
import asyncio 
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI()


HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 10


@app.get("/client")
async def home():
    return FileResponse("static/heartbeat.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    receiver_task = asyncio.create_task(receive_messages(websocket))
    heartbeat_task = asyncio.create_task(send_heartbeat(websocket))

    done, pending = await asyncio.wait(
        [receiver_task, heartbeat_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()



async def receive_messages(websocket: WebSocket):
    """Wait for messages from the client. Raises WebSocketDisconnect when they leave."""
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Got: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")
        raise



async def send_heartbeat(websocket: WebSocket):
    """Periodically ping. If a ping fials, the conntection is dead"""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)

        try:
            await websocket.send_text("__ping__")
            print("Sent ping")

        except Exception:
            print("Heartbeat failed, closing")
            await websocket.close()
            return

