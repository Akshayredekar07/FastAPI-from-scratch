# examples/08_typed_messages.py
from datetime import datetime
from typing import Literal
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from fastapi.responses import FileResponse


app = FastAPI()


# ---- Define the shape of every message we send/receive

class ChatMessage(BaseModel):
    type: Literal["chat"] = "chat"
    user: str
    text: str


class JoinMessage(BaseModel):
    type: Literal["join"] = "join"
    user: str


class LeaveMessage(BaseModel):
    type: Literal["leave"] = "leave"
    user: str


class ServerMessage(BaseModel):
    """What the server sends back to clients."""
    type: Literal["chat", "system", "user_list"]
    user: str | None = None
    text: str | None = None
    users: list[str] | None = None
    timestamp: str


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, WebSocket] = {}  # username -> WebSocket

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[username] = websocket

    def disconnect(self, username: str):
        self.connections.pop(username, None)

    async def broadcast(self, message: ServerMessage):
        # Convert to JSON string once, send to all
        text = message.model_dump_json()
        for conn in self.connections.values():
            await conn.send_text(text)


manager = ConnectionManager()


def make_system_message(text: str) -> ServerMessage:
    return ServerMessage(
        type="system",
        text=text,
        timestamp=datetime.now().isoformat(),
    )


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)

    # Tell everyone a new user joined
    await manager.broadcast(make_system_message(f"{username} joined"))
    await manager.broadcast(ServerMessage(
        type="user_list",
        users=list(manager.connections.keys()),
        timestamp=datetime.now().isoformat(),
    ))

    try:
        while True:
            raw = await websocket.receive_text()

            # Try to parse as ChatMessage. If shape is wrong, ignore.
            try:
                msg = ChatMessage.model_validate_json(raw)
            except ValidationError as e:
                await websocket.send_text(f'{{"type":"error","text":"{e}"}}')
                continue

            # Broadcast the chat message
            await manager.broadcast(ServerMessage(
                type="chat",
                user=msg.user,
                text=msg.text,
                timestamp=datetime.now().isoformat(),
            ))

    except WebSocketDisconnect:
        manager.disconnect(username)
        await manager.broadcast(make_system_message(f"{username} left"))
        await manager.broadcast(ServerMessage(
            type="user_list",
            users=list(manager.connections.keys()),
            timestamp=datetime.now().isoformat(),
        ))

