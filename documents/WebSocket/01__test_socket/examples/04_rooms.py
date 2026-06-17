from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI()


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        if room not in self.rooms:
            self.rooms[room] = []
        self.rooms[room].append(websocket)


    def disconnect(self, room: str, websocket: WebSocket):
        if room in self.rooms:
            self.rooms[room].remove(websocket)
            if not self.rooms[room]:
                # Clean up empty rooms
                del self.rooms[room]

    async def broadcast_to_room(self, room: str, message: str):
        if room in self.rooms:
            for connection in self.rooms[room]:
                await connection.send_text(message)


manager = RoomManager()



@app.get("/client")
async def client():
    return FileResponse("static/testrooms.html")


@app.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str):
    await manager.connect(room, websocket)
    await manager.broadcast_to_room(room, f"--> Someone joined #{room}")
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast_to_room(room, data)
    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
        await manager.broadcast_to_room(room, f"<-- Someone left #{room}")