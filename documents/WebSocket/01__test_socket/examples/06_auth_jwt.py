
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, WebSocket, Query
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import FileResponse

app=FastAPI()


SECRET_KEY = "24591626-bae1-49e7-82b1-15fa50565477"
ALGORITHM = "HS256"


def create_token(user_id: str, expire_in_minutes: int = 60):
    """Helper to create a JWT for testing. In real life, you'd do this in a /login HTTP endpoint."""
    payload = {
        "sub": user_id, 
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_in_minutes)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str)->str|None:
    """Returns user_id if valid, None if invalid/expired."""
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        return payload.get("sub")
    except jwt.PyJWTError:
        return None



@app.get("/client")
async def home():
    return FileResponse("static/userauth.html")


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    user_id = verify_token(token)
    if not user_id:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    await websocket.accept()
    print(f"User '{user_id}' authenticated and connected")

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"[{user_id}] echo: {data}")
    except WebSocketDisconnect:
        print(f"User '{user_id}' disconnected")


@app.get("/token/{user_id}")
def get_token(user_id: str):
    return {"token": create_token(user_id)}