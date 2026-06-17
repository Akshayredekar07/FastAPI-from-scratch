import asyncio
import json
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.websockets import WebSocketDisconnect

# ══════════════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════════════

REDIS_URL = "redis://localhost:6379"
CHANNEL = "chat:general"

# ── Why these params ──────────────────────────────────────────────────────────
# socket_timeout=None   -> pubsub read blocks indefinitely; no spurious timeouts
# socket_connect_timeout=5 -> still fail fast on initial connect
# health_check_interval=30 -> sends PING every 30s so idle connections stay alive
# socket_keepalive=True -> OS-level TCP keepalive, survives NAT timeouts in WSL
# ─────────────────────────────────────────────────────────────────────────────

redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=None,          # ← critical fix: no timeout on blocking reads
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


# ══════════════════════════════════════════════════════════════════════════════
# PubSub Manager
# ══════════════════════════════════════════════════════════════════════════════

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
        """
        Subscribes to Redis channel and fans out messages to local WebSocket
        clients on this worker.

        Uses get_message(timeout=1.0) instead of listen() so the coroutine
        yields to the event loop every second. listen() blocks the socket
        indefinitely and combined with socket_timeout (default=5s in redis-py)
        was causing the repeated TimeoutError -> reconnect loop.
        """
        print("[LISTENER] Redis listener started")
        retry_delay = 2

        while True:
            pubsub = None
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(CHANNEL)
                print("[OK] Subscribed to Redis channel")

                # ── Message loop ──────────────────────────────────────────────
                # timeout=1.0 -> returns None after 1s of no messages instead of
                # blocking; lets asyncio schedule other coroutines in between.
                # ignore_subscribe_messages=True -> skips the confirmation frame.
                # ─────────────────────────────────────────────────────────────
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )

                    if message is None:
                        # No message this poll — yield and try again
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
                # App is shutting down — exit cleanly
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


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

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