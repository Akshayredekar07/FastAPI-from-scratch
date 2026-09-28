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