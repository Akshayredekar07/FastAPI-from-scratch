# Redis PubSub Timeout Loop — Debug & Fix Reference

**Stack:** FastAPI + `redis.asyncio` + uvicorn multi-worker  
**Symptom:** Repeated `Timeout reading from localhost:6379` every 2s with constant reconnect loop  
**Status:** Resolved  

---

## What the Error Looked Like

```
✅ Subscribed to Redis channel
❌ Listener error (reconnecting in 2s): Timeout reading from localhost:6379
✅ Subscribed to Redis channel
❌ Listener error (reconnecting in 2s): Timeout reading from localhost:6379
```

This repeats infinitely. Messages still delivered (sometimes), but logs are flooded and
the system wastes CPU reconnecting constantly.

---

## Step 1 — Debug WSL + Redis First (Before Touching Code)

Always verify Redis is actually healthy before assuming the code is wrong.

### 1.1 Check if Redis is running

```bash
sudo service redis-server status
```

Expected output includes: `Active: active (running)` and `Status: "Ready to accept connections"`

If not running:

```bash
sudo service redis-server start
```

> ⚠️ **WSL does not persist services across reboots.** You must start Redis manually
> every time you open a new WSL session unless you configure autostart.

### 1.2 Confirm Redis responds

```bash
redis-cli ping
# Expected: PONG

redis-cli -h 127.0.0.1 -p 6379 ping
# Expected: PONG
```

### 1.3 Check if port 6379 is actually bound

```bash
ss -tlnp | grep 6379
```

Expected output:

```
LISTEN 0   511   127.0.0.1:6379   0.0.0.0:*
LISTEN 0   511       [::1]:6379      [::]:*
```

If nothing shows up, Redis is not listening — restart it.

### 1.4 Test pub/sub manually (two terminals)

Terminal 1:

```bash
redis-cli subscribe chat:general
```

Terminal 2:

```bash
redis-cli publish chat:general "hello"
# Expected: (integer) 1   ← means 1 subscriber received it
```

Terminal 1 should print:

```
1) "message"
2) "chat:general"
3) "hello"
```

### 1.5 Test if idle connection stays open

Leave Terminal 1 subscribed with no messages for 2+ minutes.

- If it stays open → Redis config is fine, problem is in Python code
- If it drops with `Error: Server closed the connection` → check Redis timeout config

### 1.6 Check Redis server timeout settings

```bash
redis-cli config get timeout
redis-cli config get tcp-keepalive
```

If `timeout` is not `0`, Redis is killing idle clients:

```bash
redis-cli config set timeout 0
redis-cli config set tcp-keepalive 60
redis-cli config rewrite    # make permanent
```

---

## Step 2 — Root Cause in the Code

Redis was healthy (`timeout=0`, `tcp-keepalive=300`, `ping` working, idle subscribe stayed
open for 2+ minutes). The problem was entirely in the Python client.

### The actual cause

`redis.asyncio.client.Redis` has **`socket_timeout=5` as the default**. This means any
socket read operation that blocks longer than 5 seconds raises:

```
TimeoutError: Timeout reading from localhost:6379
```

The `pubsub.listen()` generator blocks the socket indefinitely waiting for the next
message. When the channel is idle for 5 seconds, it hits the default `socket_timeout`,
throws `TimeoutError`, the `except` block catches it, closes and reopens the pubsub
connection, and the whole cycle repeats every 5 seconds forever.

### Secondary cause

`pubsub.listen()` is an async generator that holds a blocking socket read. It does not
yield to the asyncio event loop between polls, which means other coroutines can be
starved when messages are flowing fast.

---

## Step 3 — Code Changes

### Change 1: Fix `from_url()` connection params

**Before:**

```python
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
```

**After:**

```python
redis_client = aioredis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=None,        # no timeout on blocking pubsub reads
    socket_connect_timeout=5,   # still fail fast on initial connect
    socket_keepalive=True,      # OS-level TCP keepalive
    health_check_interval=30,   # PING every 30s to keep idle conn alive
)
```

| Param | Value | Why |
|---|---|---|
| `socket_timeout` | `None` | Removes the 5s default that was causing `TimeoutError` on idle reads |
| `socket_connect_timeout` | `5` | Still fail fast if Redis is unreachable at startup |
| `socket_keepalive` | `True` | OS sends TCP keepalive probes — prevents NAT/firewall dropping the connection in WSL |
| `health_check_interval` | `30` | redis-py sends a PING every 30s of idle time; keeps connection alive at the application layer |

### Change 2: Replace `listen()` with `get_message(timeout=1.0)`

**Before:**

```python
async for message in pubsub.listen():
    if message["type"] != "message":
        continue
    # process message
```

**After:**

```python
while True:
    message = await pubsub.get_message(
        ignore_subscribe_messages=True,
        timeout=1.0,
    )

    if message is None:
        await asyncio.sleep(0)   # yield to event loop
        continue

    # process message
```

| | `listen()` | `get_message(timeout=1.0)` |
|---|---|---|
| Blocks event loop | Yes — holds socket read indefinitely | No — returns `None` after 1s, yields control |
| Works with `socket_timeout=None` | Blocks forever on idle channel | Polls every 1s, cooperative with asyncio |
| Auto-skips subscribe frames | No — must check `message["type"]` | Yes — `ignore_subscribe_messages=True` |
| Used internally by redis-py's `pubsub.run()` | No | Yes — this is the same pattern |

### Change 3: Proper pubsub cleanup in `finally`

**Before:**

```python
finally:
    if pubsub:
        try:
            await pubsub.unsubscribe(CHANNEL)
        except:
            pass
```

**After:**

```python
finally:
    if pubsub:
        try:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()    # explicitly close the pubsub connection
        except Exception:
            pass
```

### Change 4: Windows cp1252 encoding — remove emoji from print statements

Running uvicorn on Windows PowerShell (cp1252 encoding) crashes if `print()` contains
Unicode emoji like `✅`, `❌`, `📤`:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2705'
```

Replace all emoji with plain ASCII tags:

| Emoji | Replace with |
|---|---|
| `✅` | `[OK]` |
| `❌` | `[ERR]` |
| `📤` | `[PUB]` |
| `📥` | `[SUB]` |
| `🔄` | `[LISTENER]` |
| `→` | `->` |

> 💡 **Tip:** If you want emoji in future scripts on Windows, add this at the top of
> the file: `import sys; sys.stdout.reconfigure(encoding='utf-8')`

---

## Final Working Code

```python
import asyncio
import json
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.websockets import WebSocketDisconnect

REDIS_URL = "redis://localhost:6379"
CHANNEL = "chat:general"

redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=None,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
        )
        await redis_client.ping()
        print("[OK] Redis connected")

        asyncio.create_task(manager.listener())
        print("[OK] Background listener started")
    except Exception as e:
        print(f"[ERR] Redis failed: {e}")

    yield

    if redis_client:
        await redis_client.aclose()


app = FastAPI(lifespan=lifespan)


class PubSubManager:
    def __init__(self):
        self.local_connections: dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.local_connections[username] = websocket
        print(f"[OK] Connected: {username} | Local users: {len(self.local_connections)}")

    def disconnect(self, username: str):
        self.local_connections.pop(username, None)
        print(f"[ERR] Disconnected: {username} | Remaining: {len(self.local_connections)}")

    async def publish(self, message: dict):
        if not redis_client:
            return
        try:
            await redis_client.publish(CHANNEL, json.dumps(message))
            print(f"[PUB] Published: {message}")
        except Exception as e:
            print(f"[ERR] Publish failed: {e}")

    async def listener(self):
        print("[LISTENER] Redis listener started")
        retry_delay = 2

        while True:
            pubsub = None
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(CHANNEL)
                print("[OK] Subscribed to Redis channel")

                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )

                    if message is None:
                        await asyncio.sleep(0)
                        continue

                    try:
                        data = json.loads(message["data"])
                        print(f"[SUB] Received from Redis: {data}")

                        disconnected = []
                        for username, ws in list(self.local_connections.items()):
                            try:
                                await ws.send_text(json.dumps(data))
                                print(f"   -> Sent to {username}")
                            except Exception:
                                disconnected.append(username)

                        for u in disconnected:
                            self.disconnect(u)

                    except Exception as e:
                        print(f"[ERR] Message processing error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERR] Listener error (reconnecting in {retry_delay}s): {e}")
            finally:
                if pubsub:
                    try:
                        await pubsub.unsubscribe(CHANNEL)
                        await pubsub.aclose()
                    except Exception:
                        pass

            await asyncio.sleep(retry_delay)


manager = PubSubManager()


@app.get("/client")
async def home():
    return FileResponse("static/redistest.html")


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)
    await manager.publish({"type": "system", "text": f"{username} joined the chat"})

    try:
        while True:
            data = await websocket.receive_text()
            await manager.publish({
                "type": "chat",
                "user": username,
                "text": data,
            })
    except WebSocketDisconnect:
        manager.disconnect(username)
        await manager.publish({"type": "system", "text": f"{username} left the chat"})
```

---

## Run Command

From the project root (`01__test_socket/`):

```bash
uvicorn examples.09_redis_scaling:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## Expected Healthy Logs

```
[OK] Redis connected
[OK] Background listener started
[LISTENER] Redis listener started
[OK] Subscribed to Redis channel
INFO:     Application startup complete.
# repeats x4 for each worker

[OK] Connected: karan | Local users: 1
[PUB] Published: {'type': 'system', 'text': 'karan joined the chat'}
[SUB] Received from Redis: {'type': 'system', 'text': 'karan joined the chat'}
   -> Sent to karan
```

No reconnect loops. No `Timeout reading from localhost:6379`. Each message appears
exactly 4 times in `[SUB]` (once per worker, since all 4 subscribe to the same channel)
and is delivered only to the locally connected client on that worker.

---

## Quick Reference

| Problem | Diagnosis Command | Fix |
|---|---|---|
| Redis not running | `sudo service redis-server status` | `sudo service redis-server start` |
| Port not bound | `ss -tlnp \| grep 6379` | Restart Redis |
| Server killing idle clients | `redis-cli config get timeout` | `redis-cli config set timeout 0` |
| Timeout loop in Python | Logs show repeated `Timeout reading` | `socket_timeout=None` in `from_url()` |
| Crash on Windows with emoji | `UnicodeEncodeError: charmap` | Replace emoji with `[OK]` / `[ERR]` etc. |
| `listen()` starving event loop | Messages delayed under load | Switch to `get_message(timeout=1.0)` |