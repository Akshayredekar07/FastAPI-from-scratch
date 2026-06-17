# **SSE with FastAPI — Complete Notes From Basic to Advanced**

---

## **Table of Contents**

1. [Setup — Install everything you need](#1-setup--install-everything-you-need)
2. [Project structure we will build](#2-project-structure-we-will-build)
3. [Example 1 — Tiny SSE server (the smallest possible)](#3-example-1--tiny-sse-server-the-smallest-possible)
4. [Example 2 — HTML/JS test client](#4-example-2--htmljs-test-client)
5. [Example 3 — Named event types (custom channels)](#5-example-3--named-event-types-custom-channels)
6. [Example 4 — Event IDs and Last-Event-ID reconnect](#6-example-4--event-ids-and-last-event-id-reconnect)
7. [Example 5 — Disconnect detection with request.is_disconnected](#7-example-5--disconnect-detection)
8. [Example 6 — Multiple clients with asyncio Queue](#8-example-6--multiple-clients-with-asyncio-queue)
9. [Example 7 — Broadcast to all connected clients](#9-example-7--broadcast-to-all-connected-clients)
10. [Example 8 — Keepalive heartbeat (prevent proxy timeouts)](#10-example-8--keepalive-heartbeat)
11. [Example 9 — Authentication with JWT (token in query param)](#11-example-9--authentication-with-jwt-token-in-query-param)
12. [Example 10 — Channels / topics (subscribe to specific streams)](#12-example-10--channels--topics)
13. [Example 11 — Scaling with Redis Pub/Sub (multiple workers)](#13-example-11--scaling-with-redis-pubsub-multiple-workers)
14. [Example 12 — AI token streaming simulation](#14-example-12--ai-token-streaming-simulation)
15. [Example 13 — Background task with progress streaming](#15-example-13--background-task-with-progress-streaming)
16. [Case Study — Real-time AI pipeline with status streaming](#16-case-study--real-time-ai-pipeline-with-status-streaming)
17. [Testing your SSE server](#17-testing-your-sse-server)
18. [Common pitfalls in FastAPI SSE](#18-common-pitfalls-in-fastapi-sse)
19. [Quick reference card](#19-quick-reference-card)

---

## **1. Setup — Install everything you need**

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate         # Linux/Mac
venv\Scripts\activate            # Windows

# Core packages
pip install fastapi
pip install uvicorn[standard]    # ASGI server for FastAPI

# SSE library — sse-starlette is the standard for FastAPI SSE
pip install sse-starlette

# Supporting packages
pip install pydantic             # Already comes with FastAPI
pip install python-jose[cryptography]  # JWT auth
pip install redis                # Redis pub/sub for scaling
pip install httpx                # For testing

# Optional
pip install python-dotenv        # Load .env config files
pip install aioredis             # Async Redis (if you prefer)
```

**Why sse-starlette?**

FastAPI is built on Starlette. The `sse-starlette` library adds proper SSE support with `EventSourceResponse` — it handles the correct headers, ping/keepalive, and disconnect detection automatically.

```bash
# Run the server
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Production (multiple workers)
uvicorn app:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## **2. Project structure we will build**

```
sse_fastapi_project/
│
├── app.py                  ← main app (starts simple, grows with examples)
├── auth.py                 ← JWT helpers
├── client_manager.py       ← manages SSE connections
├── requirements.txt
│
├── templates/
│   └── index.html          ← test HTML client
│
└── examples/
    ├── example1_basic.py
    ├── example6_queue.py
    ├── example11_redis.py
    └── example16_casestudy.py
```

---

## **3. Example 1 — Tiny SSE server (the smallest possible)**

This is the absolute minimum FastAPI SSE server. Read this first.

```python
# example1_basic.py
import asyncio
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()


async def event_generator():
    """
    An async generator that yields events.
    Each yield sends one event to the client.
    """
    count = 0
    while True:
        count += 1
        # Simplest format: just a dict with "data" key
        yield {"data": f"Message number {count}"}
        await asyncio.sleep(1)  # Wait 1 second (async — non-blocking)


@app.get("/events")
async def sse_endpoint():
    # EventSourceResponse wraps your generator and sets all correct headers
    return EventSourceResponse(event_generator())


@app.get("/")
async def root():
    return {"message": "Go to /events for SSE stream"}


# Run with: uvicorn example1_basic:app --reload
```

**What is happening:**

```
Browser                              FastAPI
  |                                     |
  |--- GET /events -------------------->|
  |                                     | ← async generator starts
  |<-- HTTP 200 ------------------------|
  |<-- Content-Type: text/event-stream  |
  |                                     |
  |<-- data: Message number 1\n\n ------|  ← after 1 second
  |<-- data: Message number 2\n\n ------|  ← after 2 seconds
  |   (connection stays open)           |
```

**The key difference from Flask:** FastAPI uses `async def` and `await asyncio.sleep()` instead of `time.sleep()`. This is non-blocking — the server can handle hundreds of SSE connections simultaneously without threads.

---

## **4. Example 2 — HTML/JS test client**

```python
# example2_with_client.py
import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()


async def event_generator():
    count = 0
    while True:
        count += 1
        # Yield a dict — sse-starlette handles JSON serialization
        yield {
            "data": json.dumps({"count": count, "message": f"Hello number {count}"}),
            "event": "update"
        }
        await asyncio.sleep(2)


@app.get("/events")
async def sse():
    return EventSourceResponse(event_generator())


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>FastAPI SSE Test</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        #status { color: green; font-weight: bold; }
        #messages { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: auto; }
        .msg { margin: 5px 0; padding: 5px; background: #f0f0f0; }
    </style>
</head>
<body>
    <h1>FastAPI SSE Live Updates</h1>
    <p>Status: <span id="status">Connecting...</span></p>
    <div id="messages"></div>
    <button onclick="stopStream()">Stop</button>

    <script>
        const eventSource = new EventSource('/events');
        const messagesDiv = document.getElementById('messages');
        const statusSpan = document.getElementById('status');

        eventSource.onopen = function() {
            statusSpan.textContent = '🟢 Connected';
        };

        // Named event: "update" — matches event: "update" in the yield dict
        eventSource.addEventListener('update', function(event) {
            const data = JSON.parse(event.data);
            const div = document.createElement('div');
            div.className = 'msg';
            div.textContent = `Count: ${data.count} | ${data.message}`;
            messagesDiv.prepend(div);
        });

        eventSource.onerror = function() {
            statusSpan.textContent = '🔴 Reconnecting...';
            statusSpan.style.color = 'red';
        };

        function stopStream() {
            eventSource.close();
            statusSpan.textContent = '⚫ Stopped';
        }
    </script>
</body>
</html>
"""
```

---

## **5. Example 3 — Named event types (custom channels)**

With `sse-starlette`, you yield a dict with keys: `data`, `event`, `id`, `retry`.

```python
import asyncio
import json
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()


async def mixed_event_generator():
    """Sends different event types at different times"""
    count = 0
    while True:
        count += 1

        if count % 5 == 0:
            # Notification event every 5 counts
            yield {
                "event": "notification",
                "data": json.dumps({"text": f"Alert! Event #{count}", "level": "warning"})
            }

        elif count % 3 == 0:
            # Price update every 3 counts
            yield {
                "event": "price-update",
                "data": json.dumps({
                    "symbol": "BTC",
                    "price": round(40000 + random.uniform(-500, 500), 2)
                })
            }

        else:
            # Default message (no event field = onmessage fires)
            yield {
                "data": json.dumps({"count": count, "type": "default"})
            }

        await asyncio.sleep(1)


@app.get("/events")
async def sse():
    return EventSourceResponse(mixed_event_generator())


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>Named Events Demo</h1>
<div id="log" style="font-family:monospace; white-space:pre; border:1px solid #ccc;
     padding:10px; height:300px; overflow:auto;"></div>

<script>
    const es = new EventSource('/events');
    const log = document.getElementById('log');

    function addLog(type, data) {
        log.textContent = `[${type}] ${JSON.stringify(data)}\n` + log.textContent;
    }

    // Catches events WITHOUT event: field
    es.onmessage = (e) => addLog('message', JSON.parse(e.data));

    // Named event listeners
    es.addEventListener('notification', (e) => addLog('🔔 NOTIFICATION', JSON.parse(e.data)));
    es.addEventListener('price-update', (e) => addLog('💰 PRICE', JSON.parse(e.data)));
</script>
</body>
</html>
"""
```

---

## **6. Example 4 — Event IDs and Last-Event-ID reconnect**

```python
import asyncio
import json
import time
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

# Simulated event store — in a real app this would be a database
EVENT_STORE = [
    {"id": i, "message": f"Stored event {i}", "ts": i * 100}
    for i in range(1, 21)
]


async def event_generator_with_id(request: Request):
    """
    Reads Last-Event-ID from request headers.
    Sends missed events first, then streams new ones.
    """
    # Check if client is reconnecting
    last_event_id = request.headers.get("last-event-id")

    if last_event_id:
        last_id = int(last_event_id)
        missed = [e for e in EVENT_STORE if e["id"] > last_id]
        print(f"Reconnect: Last-Event-ID={last_id}, sending {len(missed)} missed events")
        for event in missed:
            yield {
                "id": str(event["id"]),
                "event": "history",
                "data": json.dumps(event)
            }
    else:
        # New client — send last 5 as history
        for event in EVENT_STORE[-5:]:
            yield {
                "id": str(event["id"]),
                "event": "history",
                "data": json.dumps(event)
            }

    # Stream new live events
    current_id = len(EVENT_STORE)
    while True:
        if await request.is_disconnected():
            print("Client disconnected")
            break

        current_id += 1
        new_event = {
            "id": current_id,
            "message": f"Live event {current_id}",
            "ts": int(time.time())
        }
        EVENT_STORE.append(new_event)

        yield {
            "id": str(new_event["id"]),
            "event": "live",
            "data": json.dumps(new_event)
        }
        await asyncio.sleep(2)


@app.get("/events")
async def sse(request: Request):
    return EventSourceResponse(event_generator_with_id(request))
```

**Reconnect flow:**
```
--- First connection ---
Server: id:16 / event:history / data:{...}
Server: id:17 / event:live    / data:{...}

--- Client disconnects (network drop) ---
--- Browser auto-reconnects ---
Client: GET /events (Last-Event-ID: 17)
Server: sees missed events from 17
Server: id:18 / event:live / data:{...}   ← resumes correctly
```

---

## **7. Example 5 — Disconnect detection**

FastAPI's `request.is_disconnected()` lets you stop the generator cleanly when the client leaves.

```python
import asyncio
import json
import time
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

app = FastAPI()
active_connections = 0


async def event_generator(request: Request, client_id: str):
    global active_connections
    active_connections += 1
    print(f"[+] {client_id} connected. Active: {active_connections}")

    try:
        count = 0
        while True:
            # Check if client has disconnected BEFORE generating next event
            if await request.is_disconnected():
                print(f"[-] {client_id} disconnected (detected via is_disconnected)")
                break

            count += 1
            yield {
                "event": "update",
                "data": json.dumps({
                    "client": client_id,
                    "count": count,
                    "active_connections": active_connections
                })
            }
            await asyncio.sleep(1)

    finally:
        # This always runs — whether client disconnects, error, or normal exit
        active_connections -= 1
        print(f"[-] {client_id} cleaned up. Active: {active_connections}")


@app.get("/events")
async def sse(request: Request, client_id: str = "anonymous"):
    return EventSourceResponse(event_generator(request, client_id))


@app.get("/status")
async def status():
    return {"active_connections": active_connections}
```

**Two ways to detect disconnect:**

```python
# Method 1: Poll inside the loop (check before each event)
if await request.is_disconnected():
    break

# Method 2: Use try/finally (cleanup always runs)
try:
    while True:
        yield event
finally:
    cleanup()  # Always runs on disconnect OR normal exit
```

---

## **8. Example 6 — Multiple clients with asyncio Queue**

FastAPI is async-first. Use `asyncio.Queue` instead of `queue.Queue` for non-blocking async operations.

```python
import asyncio
import json
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# {client_id: asyncio.Queue}
clients: dict[str, asyncio.Queue] = {}


def add_client(client_id: str) -> asyncio.Queue:
    q = asyncio.Queue(maxsize=100)
    clients[client_id] = q
    print(f"[+] {client_id} connected. Total: {len(clients)}")
    return q


def remove_client(client_id: str):
    clients.pop(client_id, None)
    print(f"[-] {client_id} disconnected. Total: {len(clients)}")


async def broadcast(data: dict, event_type: str = "message"):
    """Push a message to all connected clients"""
    message = {
        "event": event_type,
        "data": json.dumps(data)
    }
    dead = []
    for cid, q in clients.items():
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dead.append(cid)
    for cid in dead:
        remove_client(cid)


async def stream_for_client(request: Request, client_id: str, q: asyncio.Queue):
    """Generator for a specific client"""
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                # Wait up to 20s for a message, then send keepalive
                message = await asyncio.wait_for(q.get(), timeout=20.0)
                yield message
            except asyncio.TimeoutError:
                yield {"data": "", "comment": "ping"}  # SSE comment = keepalive
    finally:
        remove_client(client_id)


@app.get("/events")
async def sse(request: Request, client_id: str = None):
    if client_id is None:
        client_id = str(uuid.uuid4())[:8]
    q = add_client(client_id)

    # Welcome event
    await q.put({
        "event": "connected",
        "data": json.dumps({"id": client_id, "msg": "Welcome!"})
    })

    return EventSourceResponse(
        stream_for_client(request, client_id, q),
        headers={"X-Accel-Buffering": "no"}
    )


@app.post("/broadcast")
async def do_broadcast(payload: dict):
    await broadcast(
        data={"text": payload.get("text", ""), "ts": asyncio.get_event_loop().time()},
        event_type=payload.get("event_type", "message")
    )
    return {"ok": True, "clients": len(clients)}


@app.post("/send/{client_id}")
async def send_to(client_id: str, payload: dict):
    q = clients.get(client_id)
    if q:
        try:
            q.put_nowait({"event": "direct", "data": json.dumps(payload)})
            return {"ok": True}
        except asyncio.QueueFull:
            return {"ok": False, "reason": "queue full"}
    return {"ok": False, "reason": "client not found"}


@app.get("/clients")
async def list_clients():
    return {"count": len(clients), "ids": list(clients.keys())}
```

---

## **9. Example 7 — Broadcast to all connected clients**

Build a clean `SSEBroadcaster` class using `asyncio.Queue`:

```python
import asyncio
import json
import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class SSEBroadcaster:
    """Clean broadcaster class using asyncio queues"""

    def __init__(self):
        self._clients: dict[str, asyncio.Queue] = {}
        self._event_counter = 0

    def connect(self, client_id: str = None) -> tuple[str, asyncio.Queue]:
        if client_id is None:
            client_id = str(uuid.uuid4())[:8]
        q = asyncio.Queue(maxsize=50)
        self._clients[client_id] = q
        print(f"[+] {client_id} connected. Total: {len(self._clients)}")
        return client_id, q

    def disconnect(self, client_id: str):
        self._clients.pop(client_id, None)
        print(f"[-] {client_id} disconnected. Total: {len(self._clients)}")

    async def broadcast(self, data: dict, event_type: str = "message"):
        """Send to all clients"""
        self._event_counter += 1
        payload = {
            "id": str(self._event_counter),
            "event": event_type,
            "data": json.dumps(data)
        }
        dead = []
        for cid, q in self._clients.items():
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)
        return len(self._clients)

    async def send_to(self, client_id: str, data: dict, event_type: str = "direct") -> bool:
        """Send to one client"""
        q = self._clients.get(client_id)
        if q:
            try:
                q.put_nowait({
                    "event": event_type,
                    "data": json.dumps(data)
                })
                return True
            except asyncio.QueueFull:
                return False
        return False

    async def stream(self, request: Request, client_id: str, q: asyncio.Queue):
        """Generator for a specific client"""
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield event
                except asyncio.TimeoutError:
                    yield {"data": "ping", "comment": "keepalive"}
        finally:
            self.disconnect(client_id)

    @property
    def count(self):
        return len(self._clients)


broadcaster = SSEBroadcaster()


class BroadcastPayload(BaseModel):
    text: str
    event_type: str = "message"


@app.get("/events")
async def sse(request: Request):
    client_id, q = broadcaster.connect()
    await q.put({
        "event": "welcome",
        "data": json.dumps({"id": client_id, "msg": "Connected!"})
    })
    return EventSourceResponse(broadcaster.stream(request, client_id, q))


@app.post("/broadcast")
async def do_broadcast(payload: BroadcastPayload):
    count = await broadcaster.broadcast(
        data={"text": payload.text, "ts": time.time()},
        event_type=payload.event_type
    )
    return {"ok": True, "sent_to": count}


@app.post("/send/{client_id}")
async def send_direct(client_id: str, payload: dict):
    ok = await broadcaster.send_to(client_id, payload)
    return {"ok": ok}


@app.get("/clients")
async def clients():
    return {"count": broadcaster.count, "ids": list(broadcaster._clients.keys())}
```

---

## **10. Example 8 — Keepalive heartbeat**

`sse-starlette` has built-in ping support. You can also do it manually.

```python
import asyncio
import json
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

app = FastAPI()


# Option A — Built-in ping from sse-starlette (recommended)
async def event_generator():
    count = 0
    while True:
        count += 1
        # Only real events every 10 seconds
        if count % 10 == 0:
            yield {"event": "update", "data": json.dumps({"count": count})}
        await asyncio.sleep(1)


@app.get("/events-auto-ping")
async def sse_auto_ping():
    return EventSourceResponse(
        event_generator(),
        ping=15,  # Send a ping comment every 15 seconds automatically
        # ping sends ": ping\n\n" — browser ignores it but connection stays alive
    )


# Option B — Manual keepalive (more control)
async def generator_with_manual_keepalive(request: Request):
    count = 0
    last_event_time = asyncio.get_event_loop().time()

    while True:
        if await request.is_disconnected():
            break

        now = asyncio.get_event_loop().time()
        elapsed = now - last_event_time

        if elapsed >= 10:
            # Real event every 10 seconds
            count += 1
            yield {"event": "update", "data": json.dumps({"count": count})}
            last_event_time = now
        else:
            # Keepalive comment every second while waiting
            yield {"comment": "keepalive"}  # sse-starlette sends ": keepalive\n\n"
            await asyncio.sleep(1)


@app.get("/events-manual-ping")
async def sse_manual_ping(request: Request):
    return EventSourceResponse(
        generator_with_manual_keepalive(request),
        headers={"X-Accel-Buffering": "no"}
    )
```

---

## **11. Example 9 — Authentication with JWT (token in query param)**

`EventSource` in the browser cannot send custom headers. Pass JWT as query param, validate with FastAPI Depends.

```python
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"


# ─── Auth models and helpers ──────────────────────────────────────────────────

class User(BaseModel):
    user_id: int
    username: str


def create_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=8)
    payload = {"user_id": user_id, "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[User]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return User(user_id=payload["user_id"], username=payload["username"])
    except JWTError:
        return None


# ─── Dependency for SSE (token in query param) ────────────────────────────────

def get_current_user_from_token(
    token: str = Query(default=None, description="JWT token for auth")
) -> User:
    """
    Dependency that reads token from query parameter.
    Use for SSE because EventSource can't send headers.
    Usage: GET /events?token=<jwt>
    """
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


# ─── Auth endpoint ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str


@app.post("/login")
async def login(body: LoginRequest):
    user_id = abs(hash(body.username)) % 100000
    token = create_token(user_id=user_id, username=body.username)
    return {"token": token, "user_id": user_id, "username": body.username}


# ─── Protected SSE endpoint ───────────────────────────────────────────────────

async def user_event_stream(user: User, request: Request):
    """Events personalized for the authenticated user"""
    count = 0
    while True:
        if await request.is_disconnected():
            break

        count += 1
        yield {
            "event": "personalized-update",
            "data": json.dumps({
                "user": user.username,
                "user_id": user.user_id,
                "count": count,
                "message": f"Hello {user.username}! Event #{count}"
            })
        }
        await asyncio.sleep(3)


@app.get("/events")
async def sse(
    request: Request,
    user: User = Depends(get_current_user_from_token)
):
    """
    Protected SSE endpoint.
    Access: GET /events?token=<your-jwt-token>
    """
    print(f"SSE connected: {user.username} (id={user.user_id})")
    return EventSourceResponse(user_event_stream(user, request))


# ─── Optional: For regular HTTP endpoints use header-based auth ───────────────

security = HTTPBearer()


def get_current_user_from_header(
    credentials = Depends(security)
) -> User:
    """For normal HTTP endpoints — reads Authorization: Bearer <token> header"""
    user = decode_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@app.get("/me")
async def me(user: User = Depends(get_current_user_from_header)):
    """Normal API endpoint with header auth"""
    return {"user_id": user.user_id, "username": user.username}
```

**Client-side:**
```javascript
// Get token
const res = await fetch('/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: 'ali'})
});
const {token} = await res.json();

// Connect SSE with token in URL
const es = new EventSource(`/events?token=${token}`);
es.addEventListener('personalized-update', (e) => console.log(JSON.parse(e.data)));
```

---

## **12. Example 10 — Channels / topics**

```python
import asyncio
import json
import uuid
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ALLOWED_CHANNELS = {"orders", "notifications", "analytics", "general", "alerts"}


class ChannelManager:
    """
    Manages clients grouped by channel.
    {channel_name: {client_id: asyncio.Queue}}
    """

    def __init__(self):
        self._channels: dict[str, dict[str, asyncio.Queue]] = {}

    def subscribe(self, channel: str, client_id: str = None) -> tuple[str, asyncio.Queue]:
        if client_id is None:
            client_id = str(uuid.uuid4())[:8]
        q = asyncio.Queue(maxsize=50)
        if channel not in self._channels:
            self._channels[channel] = {}
        self._channels[channel][client_id] = q
        print(f"[+] {client_id} → '{channel}'. Channel size: {len(self._channels[channel])}")
        return client_id, q

    def unsubscribe(self, channel: str, client_id: str):
        ch = self._channels.get(channel, {})
        ch.pop(client_id, None)
        print(f"[-] {client_id} ← '{channel}'")

    async def publish(self, channel: str, data: dict, event_type: str = "message"):
        """Publish to all clients in a channel"""
        ch = self._channels.get(channel, {})
        if not ch:
            return 0
        payload = {
            "event": event_type,
            "data": json.dumps(data)
        }
        dead = []
        for cid, q in ch.items():
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(cid)
        for cid in dead:
            self.unsubscribe(channel, cid)
        return len(ch) - len(dead)

    async def stream(self, request: Request, channel: str, client_id: str, q: asyncio.Queue):
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield event
                except asyncio.TimeoutError:
                    yield {"comment": "ping"}
        finally:
            self.unsubscribe(channel, client_id)

    def subscriber_count(self, channel: str) -> int:
        return len(self._channels.get(channel, {}))

    def all_stats(self) -> dict:
        return {ch: len(clients) for ch, clients in self._channels.items()}


manager = ChannelManager()


@app.get("/events/{channel}")
async def sse_channel(channel: str, request: Request, client_id: str = None):
    """
    Subscribe to a specific channel:
    GET /events/orders
    GET /events/notifications
    GET /events/analytics
    """
    if channel not in ALLOWED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found")

    cid, q = manager.subscribe(channel, client_id)

    # Welcome event
    await q.put({
        "event": "subscribed",
        "data": json.dumps({"channel": channel, "client_id": cid})
    })

    return EventSourceResponse(
        manager.stream(request, channel, cid, q),
        headers={"X-Accel-Buffering": "no"}
    )


class PublishPayload(BaseModel):
    event_type: str = "message"
    data: dict


@app.post("/publish/{channel}")
async def publish(channel: str, payload: PublishPayload):
    """Publish an event to a channel"""
    if channel not in ALLOWED_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not found")
    sent = await manager.publish(channel, payload.data, payload.event_type)
    return {"ok": True, "sent_to": sent}


@app.get("/channels")
async def channel_stats():
    return manager.all_stats()
```

**Test:**
```bash
# Subscribe to orders channel
curl -N "http://localhost:8000/events/orders?client_id=user1"

# Publish to orders channel
curl -X POST http://localhost:8000/publish/orders \
  -H "Content-Type: application/json" \
  -d '{"event_type": "order-placed", "data": {"order_id": "ORD001", "amount": 2500}}'
```

---

## **13. Example 11 — Scaling with Redis Pub/Sub (multiple workers)**

When you run `uvicorn --workers 4`, each worker has its own memory. In-memory queues don't share across workers. Redis solves this.

```python
import asyncio
import json
import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as aioredis  # pip install redis

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

REDIS_URL = "redis://localhost:6379"
REDIS_CHANNEL = "sse_broadcast"


class RedisSSEManager:
    """
    Uses Redis Pub/Sub so broadcasts work across all worker processes.
    Each worker subscribes to Redis and forwards messages to its local clients.
    """

    def __init__(self):
        self._local_clients: dict[str, asyncio.Queue] = {}
        self._redis: aioredis.Redis = None
        self._pubsub = None
        self._listener_task = None

    async def startup(self):
        """Call this on app startup — connects to Redis and starts listener"""
        self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(REDIS_CHANNEL)
        # Start background task that listens to Redis
        self._listener_task = asyncio.create_task(self._redis_listener())
        print("Redis SSE manager started")

    async def shutdown(self):
        """Call this on app shutdown"""
        if self._listener_task:
            self._listener_task.cancel()
        if self._pubsub:
            await self._pubsub.unsubscribe()
        if self._redis:
            await self._redis.aclose()

    async def _redis_listener(self):
        """Background task: listens to Redis and forwards to local clients"""
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    raw = message["data"]
                    # Forward to all LOCAL clients on THIS worker
                    dead = []
                    for cid, q in self._local_clients.items():
                        try:
                            q.put_nowait(raw)
                        except asyncio.QueueFull:
                            dead.append(cid)
                    for cid in dead:
                        self._local_clients.pop(cid, None)
        except asyncio.CancelledError:
            pass

    def add_client(self, client_id: str) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self._local_clients[client_id] = q
        return q

    def remove_client(self, client_id: str):
        self._local_clients.pop(client_id, None)

    async def publish(self, data: dict, event_type: str = "message", event_id: str = None):
        """
        Publish via Redis — ALL workers will receive and forward to their clients.
        """
        lines = []
        if event_id:
            lines.append(f"id: {event_id}")
        lines.append(f"event: {event_type}")
        lines.append(f"data: {json.dumps(data)}")
        sse_message = "\n".join(lines) + "\n\n"
        await self._redis.publish(REDIS_CHANNEL, sse_message)

    async def stream(self, request: Request, client_id: str, q: asyncio.Queue):
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # q holds raw SSE strings (already formatted by _redis_listener)
                    raw_message = await asyncio.wait_for(q.get(), timeout=20.0)
                    # Yield as raw string
                    yield raw_message
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            self.remove_client(client_id)


manager = RedisSSEManager()


@app.on_event("startup")
async def startup():
    await manager.startup()


@app.on_event("shutdown")
async def shutdown():
    await manager.shutdown()


@app.get("/events")
async def sse(request: Request):
    client_id = str(uuid.uuid4())[:8]
    q = manager.add_client(client_id)
    # Welcome
    await q.put(f"event: connected\ndata: {json.dumps({'id': client_id})}\n\n")
    return EventSourceResponse(
        manager.stream(request, client_id, q),
        headers={"X-Accel-Buffering": "no"}
    )


@app.post("/publish")
async def publish(payload: dict):
    event_id = str(int(time.time() * 1000))
    await manager.publish(
        data=payload,
        event_type=payload.pop("event_type", "message"),
        event_id=event_id
    )
    return {"ok": True}


# Run with: uvicorn app:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## **14. Example 12 — AI token streaming simulation**

```python
import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

FAKE_RESPONSES = {
    "weather": "The weather today is looking quite nice. Temperatures will be around 25 degrees with light clouds and a gentle breeze from the southwest.",
    "python": "Python is a high-level programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991.",
    "fastapi": "FastAPI is a modern web framework for building APIs with Python. It is based on standard Python type hints and provides automatic documentation via Swagger UI.",
    "default": "I am an AI assistant and I can help you with many things. Just ask me a question and I will do my best to answer it clearly and concisely."
}


async def stream_ai_response(question: str, request: Request):
    """
    Streams a response token by token — simulates LLM streaming.
    This is exactly how OpenAI/Claude streaming APIs work.
    """
    q = question.lower()
    if "weather" in q:
        response_text = FAKE_RESPONSES["weather"]
    elif "python" in q:
        response_text = FAKE_RESPONSES["python"]
    elif "fastapi" in q:
        response_text = FAKE_RESPONSES["fastapi"]
    else:
        response_text = FAKE_RESPONSES["default"]

    tokens = [word + " " for word in response_text.split()]

    # Send "thinking" status
    yield {
        "event": "thinking",
        "data": json.dumps({"status": "thinking", "question": question})
    }
    await asyncio.sleep(0.3)

    # Stream tokens
    for i, token in enumerate(tokens):
        if await request.is_disconnected():
            break
        yield {
            "event": "token",
            "data": json.dumps({
                "token": token,
                "index": i + 1,
                "total": len(tokens),
                "done": False
            })
        }
        await asyncio.sleep(0.04)  # ~25 tokens per second

    # Done signal
    yield {
        "event": "done",
        "data": json.dumps({
            "total_tokens": len(tokens),
            "done": True
        })
    }


@app.get("/chat/stream")
async def chat_stream(request: Request, question: str = "tell me something"):
    """
    GET /chat/stream?question=what+is+python
    """
    return EventSourceResponse(
        stream_ai_response(question, request),
        headers={"X-Accel-Buffering": "no"}
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>AI Chat Streaming Demo (FastAPI)</h1>
<input id="question" value="What is FastAPI?" style="width:400px; padding:8px">
<button onclick="ask()">Ask</button>
<div id="answer" style="margin-top:20px; padding:15px; border:1px solid #ccc;
     min-height:100px; font-size:18px; line-height:1.6; white-space:pre-wrap;"></div>
<p id="status" style="color: gray;"></p>

<script>
let currentES = null;

function ask() {
    const question = document.getElementById('question').value;
    const answer = document.getElementById('answer');
    const status = document.getElementById('status');

    if (currentES) currentES.close();
    answer.textContent = '';
    status.textContent = '';

    currentES = new EventSource('/chat/stream?question=' + encodeURIComponent(question));

    currentES.addEventListener('thinking', () => {
        status.textContent = '⏳ AI is thinking...';
    });

    currentES.addEventListener('token', (e) => {
        const data = JSON.parse(e.data);
        answer.textContent += data.token;
        status.textContent = `📝 Streaming... (${data.index}/${data.total})`;
    });

    currentES.addEventListener('done', (e) => {
        const data = JSON.parse(e.data);
        status.textContent = `✅ Done! ${data.total_tokens} tokens`;
        currentES.close();
    });

    currentES.onerror = () => {
        status.textContent = '❌ Error';
        currentES.close();
    };
}
</script>
</body>
</html>
"""
```

---

## **15. Example 13 — Background task with progress streaming**

```python
import asyncio
import json
import uuid
import time
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# job_id -> asyncio.Queue for progress updates
job_queues: dict[str, asyncio.Queue] = {}


async def run_task(job_id: str, task_name: str, total_steps: int):
    """
    Long running async task — sends progress to its queue.
    """
    q = job_queues.get(job_id)
    if not q:
        return

    async def send(event_type: str, data: dict):
        await q.put({"event": event_type, "data": json.dumps(data)})

    try:
        await send("started", {"job_id": job_id, "task": task_name, "total": total_steps})

        for step in range(1, total_steps + 1):
            await asyncio.sleep(0.5)  # Simulate work (non-blocking)
            progress = int((step / total_steps) * 100)
            await send("progress", {
                "step": step,
                "total": total_steps,
                "percent": progress,
                "message": f"Processing step {step}/{total_steps}..."
            })

        await send("completed", {
            "job_id": job_id,
            "message": f"'{task_name}' finished successfully!",
            "result": {"processed": total_steps, "success": True}
        })

    except Exception as e:
        await send("error", {"job_id": job_id, "error": str(e)})

    finally:
        # Keep queue alive for 60s in case client reconnects
        await asyncio.sleep(60)
        job_queues.pop(job_id, None)


class StartTaskRequest(BaseModel):
    task_name: str = "data_processing"
    steps: int = 10


@app.post("/tasks/start")
async def start_task(body: StartTaskRequest, background_tasks: BackgroundTasks):
    """Start a task and return job_id for tracking"""
    job_id = str(uuid.uuid4())[:8]
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    job_queues[job_id] = q

    # Add task to FastAPI background tasks (runs after response is sent)
    background_tasks.add_task(run_task, job_id, body.task_name, body.steps)

    return {"job_id": job_id, "task_name": body.task_name}


@app.get("/tasks/{job_id}/progress")
async def task_progress(job_id: str, request: Request):
    """SSE stream for a specific job's progress"""
    q = job_queues.get(job_id)
    if not q:
        raise HTTPException(status_code=404, detail="Job not found")

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield event
                    # Stop after "completed" or "error"
                    if event.get("event") in ("completed", "error"):
                        break
                except asyncio.TimeoutError:
                    yield {"comment": "waiting"}
        except Exception:
            pass

    return EventSourceResponse(generate(), headers={"X-Accel-Buffering": "no"})


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>Background Task Progress (FastAPI)</h1>
<button onclick="startTask()">Start Task (10 steps)</button>
<div style="margin:10px 0; background:#eee; width:100%; height:25px; border-radius:4px; overflow:hidden">
    <div id="bar" style="width:0%; height:100%; background:#4CAF50; transition:width 0.3s; text-align:center; line-height:25px; color:white">0%</div>
</div>
<div id="log" style="font-family:monospace; border:1px solid #ccc; padding:10px; height:200px; overflow:auto"></div>

<script>
async function startTask() {
    const log = document.getElementById('log');
    const bar = document.getElementById('bar');
    log.innerHTML = '';
    bar.style.width = '0%';
    bar.textContent = '0%';

    const res = await fetch('/tasks/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task_name: 'demo_task', steps: 10})
    });
    const {job_id} = await res.json();
    log.innerHTML = `Job started: ${job_id}<br>`;

    const es = new EventSource(`/tasks/${job_id}/progress`);

    es.addEventListener('started',   (e) => {
        const d = JSON.parse(e.data);
        log.innerHTML += `✅ Task started: ${d.task}<br>`;
    });
    es.addEventListener('progress',  (e) => {
        const d = JSON.parse(e.data);
        bar.style.width = d.percent + '%';
        bar.textContent = d.percent + '%';
        log.innerHTML += `📊 ${d.percent}% — ${d.message}<br>`;
        log.scrollTop = log.scrollHeight;
    });
    es.addEventListener('completed', (e) => {
        const d = JSON.parse(e.data);
        bar.style.width = '100%';
        bar.textContent = '100%';
        log.innerHTML += `🎉 ${d.message}<br>`;
        es.close();
    });
    es.addEventListener('error',     (e) => {
        log.innerHTML += `❌ Error occurred<br>`;
        es.close();
    });
}
</script>
</body>
</html>
"""
```

---

## **16. Case Study — Real-time AI pipeline with status streaming**

**What we are building:** A pipeline where users submit a document, it goes through multiple processing steps (extract → analyze → summarize → store), and they see live status updates for each step.

```
User submits document
      ↓
FastAPI creates job and returns job_id immediately
      ↓
Background task runs the pipeline steps
      ↓
Each step sends status via SSE to the waiting client
```

**`pipeline.py`**
```python
import asyncio
import json
import time
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


async def process_document_pipeline(job_id: str, document: str, progress_queue: asyncio.Queue):
    """
    Simulates a multi-step document processing pipeline.
    Each step sends a status event to the queue.
    """

    steps = [
        ("extract",   "Extracting text from document",        0.8),
        ("analyze",   "Analyzing content and entities",       1.2),
        ("summarize", "Generating AI summary",                1.5),
        ("validate",  "Validating output quality",            0.6),
        ("store",     "Saving results to database",           0.5),
    ]

    results = {}
    total_steps = len(steps)

    async def send(event_type: str, data: dict):
        await progress_queue.put({
            "event": event_type,
            "data": json.dumps(data)
        })

    # Pipeline started
    await send("pipeline-started", {
        "job_id": job_id,
        "total_steps": total_steps,
        "document_length": len(document)
    })

    for i, (step_id, step_name, duration) in enumerate(steps):
        step_num = i + 1
        overall_progress = int(((i) / total_steps) * 100)

        # Step started
        await send("step-started", {
            "step_id": step_id,
            "step_name": step_name,
            "step_num": step_num,
            "total_steps": total_steps,
            "overall_progress": overall_progress
        })

        try:
            # Simulate actual processing
            await asyncio.sleep(duration)

            # Fake result for this step
            step_result = {
                "extract":   {"chars": len(document), "words": len(document.split())},
                "analyze":   {"entities": 5, "keywords": ["python", "fastapi", "sse"]},
                "summarize": {"summary": "Document discusses real-time SSE patterns.", "sentences": 1},
                "validate":  {"score": 0.92, "valid": True},
                "store":     {"doc_id": f"DOC-{job_id}", "saved": True}
            }.get(step_id, {})

            results[step_id] = step_result

            # Step completed
            await send("step-completed", {
                "step_id": step_id,
                "step_name": step_name,
                "step_num": step_num,
                "result": step_result,
                "overall_progress": int((step_num / total_steps) * 100)
            })

        except Exception as e:
            await send("step-failed", {
                "step_id": step_id,
                "step_name": step_name,
                "error": str(e)
            })
            await send("pipeline-failed", {"job_id": job_id, "failed_at": step_id})
            return

    # All done
    await send("pipeline-completed", {
        "job_id": job_id,
        "results": results,
        "duration_estimate": sum(d for _, _, d in steps),
        "success": True
    })
```

**`app.py`**
```python
import asyncio
import json
import uuid
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from pipeline import process_document_pipeline

app = FastAPI(title="Document Processing Pipeline")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

job_queues: dict[str, asyncio.Queue] = {}


class SubmitRequest(BaseModel):
    document: str
    title: str = "Untitled"


@app.post("/pipeline/submit")
async def submit_document(body: SubmitRequest, background_tasks: BackgroundTasks):
    """Submit a document for processing — returns job_id immediately"""
    job_id = str(uuid.uuid4())[:8]
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    job_queues[job_id] = q

    # Run pipeline in background
    background_tasks.add_task(
        process_document_pipeline,
        job_id,
        body.document,
        q
    )

    return {
        "job_id": job_id,
        "title": body.title,
        "status": "submitted",
        "stream_url": f"/pipeline/{job_id}/stream"
    }


@app.get("/pipeline/{job_id}/stream")
async def pipeline_stream(job_id: str, request: Request):
    """SSE stream for a pipeline job's progress"""
    q = job_queues.get(job_id)
    if not q:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=60.0)
                    yield event
                    # Stop after final events
                    event_type = event.get("event", "")
                    if event_type in ("pipeline-completed", "pipeline-failed"):
                        # Keep connection open 2 more seconds so client gets the final event
                        await asyncio.sleep(2)
                        break
                except asyncio.TimeoutError:
                    yield {"comment": "waiting"}
        finally:
            job_queues.pop(job_id, None)

    return EventSourceResponse(generate(), headers={"X-Accel-Buffering": "no"})


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<head>
<title>AI Pipeline Demo</title>
<style>
  body { font-family: Arial; margin: 20px; max-width: 700px; }
  textarea { width: 100%; height: 100px; padding: 8px; }
  .step { display: flex; align-items: center; margin: 8px 0; padding: 10px;
          border: 1px solid #ddd; border-radius: 4px; }
  .step-icon { margin-right: 10px; font-size: 20px; width: 30px; }
  .step.done   { background: #e8f5e9; border-color: #4caf50; }
  .step.running{ background: #fff3e0; border-color: #ff9800; }
  .step.failed { background: #ffebee; border-color: #f44336; }
  .step.pending{ background: #f5f5f5; }
  #progress-bar { width:100%; background:#eee; height:20px; border-radius:10px; overflow:hidden; margin:10px 0; }
  #bar { width:0%; height:100%; background:#4CAF50; transition:width 0.5s; }
</style>
</head>
<body>
<h1>Document Processing Pipeline</h1>
<textarea id="doc">FastAPI is a modern Python web framework built on top of Starlette and Pydantic. It provides automatic OpenAPI documentation and is known for its high performance comparable to Node.js and Go. The framework makes heavy use of Python type hints to validate request and response data.</textarea>
<br><button onclick="process()" style="padding:10px 20px; background:#007bff; color:white; border:none; cursor:pointer; border-radius:4px;">Process Document</button>

<div id="progress-bar"><div id="bar"></div></div>

<div id="steps">
  <div class="step pending" id="step-extract"><span class="step-icon">⏳</span>Extract text</div>
  <div class="step pending" id="step-analyze"><span class="step-icon">⏳</span>Analyze content</div>
  <div class="step pending" id="step-summarize"><span class="step-icon">⏳</span>Generate summary</div>
  <div class="step pending" id="step-validate"><span class="step-icon">⏳</span>Validate output</div>
  <div class="step pending" id="step-store"><span class="step-icon">⏳</span>Save to database</div>
</div>

<div id="result" style="margin-top:20px; padding:15px; background:#f0f0f0; display:none; border-radius:4px;"></div>

<script>
async function process() {
    const doc = document.getElementById('doc').value;
    document.getElementById('result').style.display = 'none';

    // Reset steps
    ['extract','analyze','summarize','validate','store'].forEach(id => {
        const el = document.getElementById('step-' + id);
        el.className = 'step pending';
        el.querySelector('.step-icon').textContent = '⏳';
    });
    document.getElementById('bar').style.width = '0%';

    // Submit document
    const res = await fetch('/pipeline/submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({document: doc, title: 'Test Doc'})
    });
    const {job_id, stream_url} = await res.json();

    // Connect SSE
    const es = new EventSource(stream_url);

    es.addEventListener('step-started', (e) => {
        const d = JSON.parse(e.data);
        const el = document.getElementById('step-' + d.step_id);
        if (el) {
            el.className = 'step running';
            el.querySelector('.step-icon').textContent = '🔄';
        }
        document.getElementById('bar').style.width = d.overall_progress + '%';
    });

    es.addEventListener('step-completed', (e) => {
        const d = JSON.parse(e.data);
        const el = document.getElementById('step-' + d.step_id);
        if (el) {
            el.className = 'step done';
            el.querySelector('.step-icon').textContent = '✅';
        }
        document.getElementById('bar').style.width = d.overall_progress + '%';
    });

    es.addEventListener('pipeline-completed', (e) => {
        const d = JSON.parse(e.data);
        document.getElementById('bar').style.width = '100%';
        const result = document.getElementById('result');
        result.style.display = 'block';
        result.innerHTML = `<b>✅ Pipeline complete!</b><br><pre>${JSON.stringify(d.results, null, 2)}</pre>`;
        es.close();
    });

    es.addEventListener('step-failed', (e) => {
        const d = JSON.parse(e.data);
        const el = document.getElementById('step-' + d.step_id);
        if (el) { el.className = 'step failed'; el.querySelector('.step-icon').textContent = '❌'; }
    });

    es.addEventListener('pipeline-failed', () => {
        es.close();
    });
}
</script>
</body>
</html>
"""
```

---

## **17. Testing your SSE server**

### **Test with curl**
```bash
# Basic connection
curl -N http://localhost:8000/events

# With query params
curl -N "http://localhost:8000/events?client_id=test1"

# With JWT token
curl -N "http://localhost:8000/events?token=your-jwt"

# See headers
curl -I http://localhost:8000/events

# Check channels
curl http://localhost:8000/channels
```

### **Test with pytest + httpx**
```python
# test_sse.py
import pytest
import asyncio
import httpx
from app import app


@pytest.mark.anyio
async def test_sse_headers():
    """SSE endpoint returns correct content type"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        async with client.stream("GET", "/events") as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]


@pytest.mark.anyio
async def test_sse_receives_events():
    """Should receive at least one event"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        async with client.stream("GET", "/events") as r:
            lines = []
            async for line in r.aiter_lines():
                lines.append(line)
                if len(lines) >= 3:  # Stop after 3 lines
                    break
            assert any("data:" in line for line in lines)


@pytest.mark.anyio
async def test_sse_format():
    """Events must contain data: field"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        async with client.stream("GET", "/events") as r:
            count = 0
            async for line in r.aiter_lines():
                if line.startswith("data:"):
                    count += 1
                    if count >= 2:
                        break
            assert count >= 2


@pytest.mark.anyio
async def test_broadcast_reaches_clients():
    """Broadcast should reach all connected clients"""
    received = []

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Connect and collect events in background
        async def collect():
            async with client.stream("GET", "/events") as r:
                async for line in r.aiter_lines():
                    if line.startswith("data:"):
                        received.append(line)
                    if len(received) >= 2:
                        break

        # Run collector and broadcaster concurrently
        collector = asyncio.create_task(collect())
        await asyncio.sleep(0.5)  # Wait for connection

        # Send broadcast
        await client.post("/broadcast", json={"text": "test broadcast", "event_type": "test"})
        await asyncio.wait_for(collector, timeout=5.0)

        assert len(received) >= 1
```

### **Test publish endpoint manually**
```bash
# Start server in one terminal
uvicorn app:app --reload

# Connect client in another terminal
curl -N "http://localhost:8000/events?client_id=c1" &

# Publish in another
curl -X POST http://localhost:8000/broadcast \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello everyone!", "event_type": "announcement"}'
```

---

## **18. Common pitfalls in FastAPI SSE**

### **Pitfall 1 — Using time.sleep() instead of asyncio.sleep()**

**Problem:** Your SSE stream blocks all other requests.

**Why:** `time.sleep()` blocks the entire async event loop. FastAPI uses asyncio — one blocked coroutine freezes everything.

**Fix:**
```python
# WRONG — blocks the event loop
import time
async def generator():
    while True:
        yield {"data": "hi"}
        time.sleep(1)  # ← BLOCKS EVERYTHING

# CORRECT — non-blocking
import asyncio
async def generator():
    while True:
        yield {"data": "hi"}
        await asyncio.sleep(1)  # ← only this coroutine waits
```

---

### **Pitfall 2 — Using threading.Queue instead of asyncio.Queue**

**Problem:** `queue.get()` blocks the event loop. Messages arrive but nothing else works.

**Fix:**
```python
# WRONG
import queue
q = queue.Queue()
msg = q.get()  # ← BLOCKING call inside async code

# CORRECT
import asyncio
q = asyncio.Queue()
msg = await q.get()  # ← non-blocking
```

---

### **Pitfall 3 — GZipMiddleware breaks SSE**

**Problem:** You add `GZipMiddleware` to your app and SSE stops working.

**Why:** GZip middleware buffers the entire response before compressing — SSE responses never end, so nothing gets sent.

**Fix:** Do not use `GZipMiddleware` if you need SSE. If you need compression on other routes, apply it selectively, not globally.

```python
# BROKEN — GZip buffers the SSE response
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware)  # ← breaks SSE

# SOLUTION: Don't add GZipMiddleware globally when using SSE
```

---

### **Pitfall 4 — Disconnect not detected without request.is_disconnected()**

**Problem:** Client closes browser. Server keeps sending events. Memory and CPU waste.

**Fix:** Always check disconnect in your loop:
```python
async def generator(request: Request):
    while True:
        if await request.is_disconnected():  # ← check this
            print("Client gone, stopping")
            break
        yield {"data": "event"}
        await asyncio.sleep(1)
```

---

### **Pitfall 5 — asyncio.Queue created outside async context**

**Problem:** You create `asyncio.Queue()` at module level or in `__init__`, and get errors about event loops.

**Why:** `asyncio.Queue` must be created inside the running event loop. Module-level init runs before the loop starts.

**Fix:**
```python
# WRONG — created at module level
my_queue = asyncio.Queue()  # ← No event loop yet

# CORRECT — create inside async context
@app.on_event("startup")
async def startup():
    app.state.my_queue = asyncio.Queue()

# Or create inside the route handler / dependency
@app.get("/events")
async def sse():
    q = asyncio.Queue()  # ← created inside async context (correct)
    ...
```

---

### **Pitfall 6 — CORS blocking SSE from browser**

**Problem:** Frontend on different port/domain gets "CORS error" when EventSource connects.

**Fix:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourfrontend.com"],
    allow_credentials=True,   # Needed for withCredentials: true in EventSource
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

### **Pitfall 7 — Multiple workers — in-memory state not shared**

**Problem:** You run `uvicorn --workers 4`. Broadcasts only reach clients on the same worker.

**Fix:** Use Redis Pub/Sub (see Example 11). Each worker subscribes to Redis and gets ALL broadcasts.

---

## **19. Quick reference card**

### **Minimal SSE endpoint**
```python
import asyncio
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

@app.get("/events")
async def sse():
    async def generate():
        while True:
            yield {"data": "hello"}
            await asyncio.sleep(1)
    return EventSourceResponse(generate())
```

### **Event dict format (sse-starlette)**
```python
yield {
    "id":      "123",           # optional — for reconnect tracking
    "event":   "my-event",      # optional — custom event type
    "data":    "your payload",  # required — the actual content
    "retry":   5000,            # optional — reconnect wait in ms
    "comment": "ping"           # optional — sends ": ping\n\n"
}
```

### **Built-in ping**
```python
EventSourceResponse(generator(), ping=15)  # Auto-ping every 15s
```

### **Disconnect detection**
```python
async def generator(request: Request):
    while True:
        if await request.is_disconnected():
            break
        yield {"data": "event"}
        await asyncio.sleep(1)
```

### **Async queue pattern**
```python
q = asyncio.Queue()
msg = await asyncio.wait_for(q.get(), timeout=20.0)  # non-blocking get with timeout
```

### **Auth via query param**
```python
from fastapi import Query, HTTPException

def get_user(token: str = Query()):
    user = decode_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

@app.get("/events")
async def sse(user = Depends(get_user)):
    ...
```

### **JS client**
```javascript
const es = new EventSource('/events?token=' + yourJWT);
es.onopen    = (e) => console.log('connected');
es.onmessage = (e) => console.log(e.data);
es.onerror   = (e) => console.log('error');
es.addEventListener('custom-event', (e) => { });
es.close();
```

### **Avoid these**
```python
time.sleep()         # Use asyncio.sleep() instead
queue.Queue()        # Use asyncio.Queue() instead
GZipMiddleware       # Breaks SSE — do not use globally
asyncio.Queue()      # at module level — create inside async context
```
