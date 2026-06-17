
# examples/02_connection_manager.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.websockets import WebSocketDisconnect

app = FastAPI()


class ConnectionManager:
    """Keeps track of all connected WebSocket clients."""
    def __init__(self) -> None:
        # Store active connections. Set is fine because WebSocket objects are hashable by id().
        # Using a list also works, but a set is slightly safer against duplicates.
        self.active_conntections: list[WebSocket] = []


    async def connect(self, websocket: WebSocket):
        """Accept the new connection and remember it."""
        await websocket.accept()
        self.active_conntections.append(websocket)
        print(f"Connected. Total: {len(self.active_conntections)}")


    async def disconnect(self, websocket: WebSocket):
        self.active_conntections.remove(websocket)
        print(f"Disconnected. Total: {len(self.active_conntections)}")


    async def send_personal(self, message: str, websocket: WebSocket):
        """Send a message to one specific client."""
        await websocket.send_text(message)


    async def broadcast(self, message: str):
        for connection in self.active_conntections:
            await connection.send_text(message)


manager = ConnectionManager()

@app.get("/testclient")
async def client():
    return FileResponse("static/client.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo to the sender only
            await manager.send_personal(f"You said: {data}", websocket)
            # And tell everyone else
            await manager.broadcast(f"Someone said: {data}")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


