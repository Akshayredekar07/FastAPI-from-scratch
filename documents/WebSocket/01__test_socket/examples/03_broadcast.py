# examples/03_broadcast.py
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Use asyncio.gather for true parallelism (faster for many clients)
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # If a client died, ignore for now; cleanup happens in disconnect()
                pass


manager = ConnectionManager()


@app.get("/testclient")
async def client():
    return FileResponse("static/client.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await manager.broadcast(f"--> A new user joined! Total: {len(manager.active_connections)}")
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"<-- A user left. Total: {len(manager.active_connections)}")