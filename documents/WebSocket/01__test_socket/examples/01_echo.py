from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.websockets import WebSocketDisconnect

app = FastAPI()


@app.get("/")
async def home():
    return FileResponse("static/index.html")


@app.get("/testclient")
async def client():
    return FileResponse("static/client.html")

@app.websocket("/ws")
async def echo_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")

            await websocket.send_text(f"Echo: {data}")

    except WebSocketDisconnect:
        print("Client disconnected")