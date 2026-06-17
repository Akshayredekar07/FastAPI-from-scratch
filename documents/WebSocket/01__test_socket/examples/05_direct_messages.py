# examples/05_direct_messages.py
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI()


class DirectMessageManager:
    def __init__(self):
        # user_id -> WebSocket connection (one connection per user)
        self.users: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        # If user already has a connection, close the old one (only one device at a time here)
        if user_id in self.users:
            try:
                await self.users[user_id].close()
            except Exception:
                pass
        self.users[user_id] = websocket

    def disconnect(self, user_id: str):
        self.users.pop(user_id, None)

    async def send_to_user(self, target_id: str, message: str) -> bool:
        """Returns True if delivered, False if user offline."""
        if target_id in self.users:
            await self.users[target_id].send_text(message)
            return True
        return False


manager = DirectMessageManager()

@app.get("/client")
async def client():
    return FileResponse("static/direct_msg.html")


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    print(f"User {user_id} connected. Online users: {list(manager.users.keys())}")

    try:
        while True:
            # Expected message format: "target_id:message"
            # e.g., "alice:hi there"
            raw = await websocket.receive_text()

            if ":" not in raw:
                await websocket.send_text("Format: target_id:message")
                continue

            target_id, message = raw.split(":", 1)
            target_id = target_id.strip()
            delivered = await manager.send_to_user(target_id, f"[from {user_id}] {message}")

            if delivered:
                await websocket.send_text(f"[sent to {target_id}] {message}")
            else:
                await websocket.send_text(f"[user {target_id} is offline]")
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        print(f"User {user_id} disconnected")