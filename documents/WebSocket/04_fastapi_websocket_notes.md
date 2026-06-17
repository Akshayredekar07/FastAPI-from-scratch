# FastAPI WebSocket — Complete Notes

## Table of Contents

1. [Setup and Installation](#1-setup-and-installation)
2. [Level 1 — Echo Server (Simplest Possible)](#2-level-1--echo-server)
3. [Level 2 — Status Emitting Server (Progress Updates)](#3-level-2--status-emitting-server)
4. [Level 3 — Connection Manager (Multiple Clients)](#4-level-3--connection-manager)
5. [Level 4 — Room-Based Broadcast (Chat Rooms)](#5-level-4--room-based-broadcast)
6. [Level 5 — Ping/Pong Heartbeat](#6-level-5--pingpong-heartbeat)
7. [Level 6 — Structured JSON Messages with Type Routing](#7-level-6--structured-json-messages)
8. [Level 7 — WebSocket + Background Task (Status Streaming)](#8-level-7--websocket--background-task)
9. [Case Study — AI Job Pipeline with Status Emitting](#9-case-study--ai-job-pipeline-with-status-emitting)
10. [Testing WebSocket Endpoints](#10-testing-websocket-endpoints)
11. [Common Errors and Fixes](#11-common-errors-and-fixes)
12. [Quick Reference Cheat Sheet](#12-quick-reference-cheat-sheet)

---

## 1. Setup and Installation

```bash
pip install fastapi uvicorn websockets
```

Run any server file with:

```bash
uvicorn filename:app --reload --host 0.0.0.0 --port 8000
```

Test with the browser HTML clients provided in each section, or use the Python test scripts.

---

## 2. Level 1 — Echo Server

### What it does

The simplest WebSocket server. Client sends a message, server echoes it back.
This covers the minimum working skeleton.

```
Client ──── "Hello" ───► Server
Client ◄─── "Echo: Hello" ── Server
```

### `01_echo_server.py`

```python
# Echo WebSocket server — simplest FastAPI WebSocket example
# websocket: the active connection object from FastAPI
# accept: must always be called before send/receive
# receive_text: blocks until client sends a text frame
# send_text: sends a text frame back to the client
# WebSocketDisconnect: raised when client closes the connection
# Precondition: client must connect to ws://localhost:8000/ws
# Time: O(1) per message | Space: O(1)
# Dry run:
#   Client connects → accept() called → state: OPEN
#   Client sends "Hello" → receive_text() returns "Hello"
#   Server calls send_text("Echo: Hello") → client receives
#   Client disconnects → WebSocketDisconnect raised → loop exits

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


@app.websocket("/ws")
async def echo_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")
```

### `01_test_echo.py` — Python test client

```python
# Test script for echo server
# asyncio: runs the async client coroutine
# websockets.connect: opens a WebSocket connection to the server
# send/recv: basic send and receive on the connection
# Precondition: echo server must be running on port 8000
# Dry run:
#   connect to ws://localhost:8000/ws → handshake → OPEN
#   send "Hello Arjun" → server echoes back → print result
#   send "Namaste" → server echoes back → print result
#   exit loop → connection closes

import asyncio
import websockets


async def test_echo():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        messages = ["Hello Arjun", "Namaste", "Testing 1 2 3"]
        for msg in messages:
            await ws.send(msg)
            response = await ws.recv()
            print(f"Sent: {msg}")
            print(f"Received: {response}")
            print()


asyncio.run(test_echo())
```

### HTML client (open in browser)

```html
<!-- 01_echo_client.html -->
<!DOCTYPE html>
<html>
<head><title>Echo Test</title></head>
<body>
  <h2>Echo WebSocket Test</h2>
  <input id="msg" placeholder="Type a message" />
  <button onclick="sendMsg()">Send</button>
  <ul id="log"></ul>

  <script>
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = () => log("Connected");
    ws.onmessage = (e) => log("Server: " + e.data);
    ws.onclose = () => log("Disconnected");

    function sendMsg() {
      const msg = document.getElementById("msg").value;
      ws.send(msg);
      log("You: " + msg);
    }

    function log(text) {
      const li = document.createElement("li");
      li.textContent = text;
      document.getElementById("log").appendChild(li);
    }
  </script>
</body>
</html>
```

---

## 3. Level 2 — Status Emitting Server

### What it does

Server sends multiple status messages to the client over time without the client asking.
This is the pattern used in AI pipelines, file processors, build systems — anywhere you want
to stream progress updates to a connected UI.

```
Client ──── connect ───────────────────────────────► Server
Client ◄─── {"status": "started",    "step": 1/5} ── Server
Client ◄─── {"status": "loading",    "step": 2/5} ── Server
Client ◄─── {"status": "processing", "step": 3/5} ── Server
Client ◄─── {"status": "saving",     "step": 4/5} ── Server
Client ◄─── {"status": "done",       "step": 5/5} ── Server
```

### `02_status_emitter.py`

```python
# Status emitting WebSocket — server pushes progress updates to client
# asyncio.sleep: simulates real work happening between steps
# send_json: FastAPI helper to serialize a dict to JSON and send as text frame
# steps: list of status strings emitted in order
# Precondition: client connects and waits; server drives the flow
# Time: O(n) where n = number of steps | Space: O(1)
# Dry run:
#   Client connects → accept() → OPEN
#   Loop step 1: send {"status": "started", "step": "1/5", "message": "..."}
#   sleep(1) → simulate work
#   Loop step 2: send {"status": "loading", ...}
#   ... continues until done
#   send final {"status": "done"} → server-side function returns → connection closes

import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

PIPELINE_STEPS = [
    {"status": "started",     "message": "Job received, initialising..."},
    {"status": "loading",     "message": "Loading data from source..."},
    {"status": "processing",  "message": "Running model inference..."},
    {"status": "saving",      "message": "Saving results to storage..."},
    {"status": "done",        "message": "Pipeline complete. Results ready."},
]


@app.websocket("/ws/status")
async def status_emitter(websocket: WebSocket):
    await websocket.accept()
    total = len(PIPELINE_STEPS)
    try:
        for i, step in enumerate(PIPELINE_STEPS, start=1):
            payload = {
                "step": f"{i}/{total}",
                "status": step["status"],
                "message": step["message"],
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.5)

        await websocket.close(code=1000)
    except WebSocketDisconnect:
        print("Client disconnected before pipeline finished")
```

### `02_test_status.py`

```python
# Test client for status emitter
# recv: blocks until server sends a frame
# json.loads: deserializes the JSON string from server
# Precondition: status emitter server running on port 8000
# Dry run:
#   connect → OPEN → wait
#   recv() returns JSON string → parse → print status + message
#   repeat until ConnectionClosedOK (server closed with 1000)

import asyncio
import json
import websockets


async def watch_status():
    uri = "ws://localhost:8000/ws/status"
    async with websockets.connect(uri) as ws:
        print("Connected. Watching pipeline status...\n")
        try:
            while True:
                raw = await ws.recv()
                data = json.loads(raw)
                print(f"[{data['step']}] {data['status'].upper()} — {data['message']}")
        except websockets.exceptions.ConnectionClosedOK:
            print("\nServer closed connection normally (1000). Pipeline done.")


asyncio.run(watch_status())
```

### Expected output

```
Connected. Watching pipeline status...

[1/5] STARTED — Job received, initialising...
[2/5] LOADING — Loading data from source...
[3/5] PROCESSING — Running model inference...
[4/5] SAVING — Saving results to storage...
[5/5] DONE — Pipeline complete. Results ready.

Server closed connection normally (1000). Pipeline done.
```

---

## 4. Level 3 — Connection Manager

### What it does

Tracks all active WebSocket connections in a manager class.
Allows the server to broadcast a message to every connected client simultaneously.

```
Rohit ──► connect → Manager.add(Rohit)
Meera ──► connect → Manager.add(Meera)
Vikram ──► connect → Manager.add(Vikram)

Server ──► broadcast("Hello everyone!") ──► Rohit, Meera, Vikram all receive
```

### `03_connection_manager.py`

```python
# Connection Manager — track multiple WebSocket clients and broadcast
# active_connections: list of all currently connected WebSocket objects
# connect: accept and register a new connection
# disconnect: remove a connection when client leaves
# broadcast: send same message to all active connections
# Precondition: multiple clients can connect concurrently
# Time: O(n) for broadcast where n = number of active connections
# Space: O(n) for storing connections
# Dry run:
#   Rohit connects → connect(ws_rohit) → active_connections = [ws_rohit]
#   Meera connects → connect(ws_meera) → active_connections = [ws_rohit, ws_meera]
#   Rohit sends "Hi" → broadcast → ws_rohit.send("Rohit: Hi"), ws_meera.send("Rohit: Hi")
#   Rohit disconnects → disconnect(ws_rohit) → active_connections = [ws_meera]

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        # connections: holds all currently active WebSocket objects
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        # accept the handshake and add to tracking list
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        # remove from list when client disconnects
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # send the message to every connected client
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{client_name}")
async def websocket_endpoint(websocket: WebSocket, client_name: str):
    await manager.connect(websocket)
    await manager.broadcast(f"[Server] {client_name} has joined. "
                            f"Total online: {len(manager.active_connections)}")
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{client_name}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"[Server] {client_name} has left. "
                                f"Total online: {len(manager.active_connections)}")
```

### `03_test_manager.py` — simulate 3 clients

```python
# Test 3 simultaneous clients connecting and chatting
# asyncio.gather: runs multiple coroutines concurrently
# each client sends 2 messages then disconnects
# Precondition: connection manager server running on port 8000

import asyncio
import websockets


async def client(name: str, messages: list, delay: float = 0):
    await asyncio.sleep(delay)
    uri = f"ws://localhost:8000/ws/{name}"
    async with websockets.connect(uri) as ws:
        # listen for server broadcast in background
        async def listener():
            try:
                while True:
                    msg = await ws.recv()
                    print(f"  [{name} sees] {msg}")
            except Exception:
                pass

        listener_task = asyncio.create_task(listener())

        for msg in messages:
            await asyncio.sleep(0.5)
            await ws.send(msg)

        await asyncio.sleep(1)
        listener_task.cancel()


async def main():
    await asyncio.gather(
        client("Rohit",  ["Hey everyone!", "How's it going?"], delay=0),
        client("Meera",  ["Hello!", "All good here."],         delay=0.2),
        client("Vikram", ["Namaste!", "Good to be here."],     delay=0.4),
    )


asyncio.run(main())
```

---

## 5. Level 4 — Room-Based Broadcast

### What it does

Clients join named rooms. Messages are broadcast only within a room, not globally.

```
Room "cricket":  Arjun, Pooja
Room "football": Karan, Tanvi

Arjun sends "Six!" → only Arjun and Pooja receive it
Karan sends "Goal!" → only Karan and Tanvi receive it
```

### `04_rooms.py`

```python
# Room-based WebSocket broadcast
# rooms: dict mapping room_name → list of WebSocket connections
# join: add client to a room, create room if it doesn't exist
# leave: remove client from room, delete room if empty
# broadcast_to_room: send message to all in the same room
# Precondition: client connects with /ws/{room}/{name}
# Time: O(r) for broadcast where r = clients in that room
# Dry run:
#   Arjun connects to /ws/cricket/Arjun → rooms = {"cricket": [ws_arjun]}
#   Pooja connects to /ws/cricket/Pooja → rooms = {"cricket": [ws_arjun, ws_pooja]}
#   Arjun sends "Six!" → broadcast_to_room("cricket", "Arjun: Six!")
#   Both Arjun and Pooja receive the message

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
from collections import defaultdict

app = FastAPI()


class RoomManager:
    def __init__(self):
        # rooms: room_name → list of active WebSocket connections
        self.rooms: Dict[str, List[WebSocket]] = defaultdict(list)

    async def join(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms[room].append(websocket)

    def leave(self, room: str, websocket: WebSocket):
        self.rooms[room].remove(websocket)
        if not self.rooms[room]:
            del self.rooms[room]

    async def broadcast_to_room(self, room: str, message: str, exclude: WebSocket = None):
        for ws in self.rooms.get(room, []):
            if ws is not exclude:
                await ws.send_text(message)

    def room_count(self, room: str) -> int:
        return len(self.rooms.get(room, []))


manager = RoomManager()


@app.websocket("/ws/{room}/{name}")
async def room_endpoint(websocket: WebSocket, room: str, name: str):
    await manager.join(room, websocket)
    await manager.broadcast_to_room(
        room,
        f"[{room}] {name} joined. Members: {manager.room_count(room)}",
        exclude=websocket
    )
    await websocket.send_text(f"[{room}] You joined. Members: {manager.room_count(room)}")

    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast_to_room(room, f"{name}: {data}")
    except WebSocketDisconnect:
        manager.leave(room, websocket)
        await manager.broadcast_to_room(
            room,
            f"[{room}] {name} left. Members: {manager.room_count(room)}"
        )
```

---

## 6. Level 5 — Ping/Pong Heartbeat

### What it does

Server sends a ping every 30 seconds. If client does not respond within 10 seconds,
assume connection is dead and close it. Prevents zombie connections.

```
Server ──► Ping (text: {"type":"ping"}) ──► Client
Client ──► Pong (text: {"type":"pong"}) ──► Server
(if no pong arrives within 10s → server closes connection)
```

> Note: Browser JS WebSocket API handles protocol-level ping/pong automatically.
> For app-level heartbeat (custom ping/pong messages), we implement it ourselves.

### `05_heartbeat.py`

```python
# WebSocket server with app-level heartbeat / ping-pong
# PING_INTERVAL: seconds between each ping
# PONG_TIMEOUT: seconds to wait for pong before declaring dead
# asyncio.wait_for: wraps a coroutine with a timeout
# asyncio.TimeoutError: raised if pong doesn't arrive in time
# Precondition: client must respond to {"type":"ping"} with {"type":"pong"}
# Time: O(1) per ping cycle | Space: O(1)
# Dry run:
#   Client connects → OPEN
#   sleep(30) → send ping → wait for recv with 10s timeout
#   If recv returns {"type":"pong"} → alive, continue loop
#   If asyncio.TimeoutError → send close(1001) → break

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

PING_INTERVAL = 30
PONG_TIMEOUT = 10


@app.websocket("/ws/heartbeat")
async def heartbeat_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    try:
        while True:
            await asyncio.sleep(PING_INTERVAL)

            await websocket.send_json({"type": "ping"})
            print("Ping sent")

            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=PONG_TIMEOUT
                )
                data = json.loads(raw)
                if data.get("type") == "pong":
                    print("Pong received — connection alive")
                else:
                    await websocket.send_text(
                        json.dumps({"error": "Expected pong, got something else"})
                    )

            except asyncio.TimeoutError:
                print("No pong — closing dead connection")
                await websocket.close(code=1001)
                break

    except WebSocketDisconnect:
        print("Client disconnected")
```

### `05_test_heartbeat.py`

```python
# Test heartbeat — client responds to pings with pongs
# json.loads: parse incoming JSON from server
# Responds to {"type":"ping"} with {"type":"pong"}
# Precondition: heartbeat server running with PING_INTERVAL=5 for testing

import asyncio
import json
import websockets


async def heartbeat_client():
    uri = "ws://localhost:8000/ws/heartbeat"
    async with websockets.connect(uri) as ws:
        print("Connected. Waiting for pings...")
        try:
            while True:
                raw = await ws.recv()
                data = json.loads(raw)
                if data.get("type") == "ping":
                    print("Ping received — sending pong")
                    await ws.send(json.dumps({"type": "pong"}))
                else:
                    print(f"Other message: {data}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: code={e.code}, reason={e.reason}")


asyncio.run(heartbeat_client())
```

---

## 7. Level 6 — Structured JSON Messages with Type Routing

### What it does

Real apps send structured JSON messages with a `type` field.
The server routes each message to a different handler based on the type.

```
Client ──► {"type": "chat",      "text": "Hello!"}      ──► broadcast to all
Client ──► {"type": "subscribe", "channel": "scores"}   ──► add to channel
Client ──► {"type": "ping"}                              ──► send {"type":"pong"}
Client ──► {"type": "status"}                            ──► send server info
```

### `06_typed_messages.py`

```python
# Typed message routing — route WebSocket messages by their "type" field
# dispatch: dict mapping type strings to handler coroutines
# ConnectionManager: same as Level 3 to support broadcast
# Each handler receives the websocket and full parsed message dict
# Precondition: client sends valid JSON with a "type" key
# Time: O(1) per dispatch lookup, O(n) for broadcast
# Dry run:
#   Client sends '{"type":"chat","text":"Hello"}' → parsed → type="chat"
#   dispatch["chat"] called → broadcast to all clients
#   Client sends '{"type":"ping"}' → dispatch["ping"] → send pong back

import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict, exclude: WebSocket = None):
        for conn in self.active:
            if conn is not exclude:
                await conn.send_json(payload)


manager = ConnectionManager()


async def handle_chat(ws: WebSocket, msg: dict):
    text = msg.get("text", "")
    sender = msg.get("sender", "anonymous")
    await manager.broadcast({"type": "chat", "sender": sender, "text": text})


async def handle_ping(ws: WebSocket, msg: dict):
    await ws.send_json({"type": "pong"})


async def handle_status(ws: WebSocket, msg: dict):
    await ws.send_json({
        "type": "status",
        "active_connections": len(manager.active),
    })


# type → handler mapping
DISPATCH = {
    "chat":   handle_chat,
    "ping":   handle_ping,
    "status": handle_status,
}


@app.websocket("/ws/typed")
async def typed_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type")
                handler = DISPATCH.get(msg_type)
                if handler:
                    await handler(websocket, msg)
                else:
                    await websocket.send_json({"error": f"Unknown type: {msg_type}"})
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

---

## 8. Level 7 — WebSocket + Background Task (Status Streaming)

### What it does

Client triggers a long-running job via WebSocket. The job runs in the background.
Status updates are pushed back to the client as the job progresses.
The job and the WebSocket listener run concurrently using `asyncio.gather`.

```
                    ┌─────────────────────────────────────┐
                    │          FastAPI Server              │
Client ──► start ──► WebSocket handler (receive loop)      │
                    │      │                               │
                    │      ├──► asyncio.create_task(job()) │
                    │      │         │                     │
                    │      │         ├──► step 1 done      │
                    │      │         ├── send status ──────► Client
                    │      │         ├──► step 2 done      │
                    │      │         ├── send status ──────► Client
                    │      │         └──► done             │
                    └─────────────────────────────────────┘
```

### `07_background_status.py`

```python
# WebSocket + background task with live status streaming
# asyncio.create_task: starts job coroutine without blocking the receive loop
# job_runner: simulates a multi-step job, sends status via websocket
# receive loop: keeps connection alive, listens for "cancel" command
# Precondition: client connects and sends {"command": "start"}
# Time: O(n) for n job steps | Space: O(1)
# Dry run:
#   Client connects → accept
#   Client sends {"command":"start"} → job_task = create_task(job_runner(ws))
#   job_runner executes step 1 → ws.send_json({"status":"step_1","done":false})
#   ... continues async while receive loop waits for next client message
#   job_runner finishes → ws.send_json({"status":"complete","done":true})

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

JOB_STEPS = [
    "Validating input data",
    "Loading pre-trained model",
    "Running inference on batch",
    "Post-processing predictions",
    "Writing output to database",
    "Generating report",
]


async def job_runner(websocket: WebSocket):
    total = len(JOB_STEPS)
    for i, step in enumerate(JOB_STEPS, start=1):
        await asyncio.sleep(1.2)
        await websocket.send_json({
            "type":    "status",
            "step":    i,
            "total":   total,
            "message": step,
            "done":    False,
        })

    await websocket.send_json({
        "type":    "status",
        "step":    total,
        "total":   total,
        "message": "Job complete. All steps finished.",
        "done":    True,
    })


@app.websocket("/ws/job")
async def job_endpoint(websocket: WebSocket):
    await websocket.accept()
    job_task = None

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            command = msg.get("command")

            if command == "start":
                if job_task and not job_task.done():
                    await websocket.send_json({"error": "Job already running"})
                else:
                    await websocket.send_json({"type": "ack", "message": "Job started"})
                    job_task = asyncio.create_task(job_runner(websocket))

            elif command == "cancel":
                if job_task and not job_task.done():
                    job_task.cancel()
                    await websocket.send_json({"type": "cancelled", "message": "Job cancelled"})
                else:
                    await websocket.send_json({"error": "No job running"})

    except WebSocketDisconnect:
        if job_task:
            job_task.cancel()
        print("Client disconnected")
```

### `07_test_background.py`

```python
# Test background job with status streaming
# Sends start command, then listens for all status updates
# Precondition: background status server running on port 8000

import asyncio
import json
import websockets
from tqdm import tqdm


async def run_job():
    uri = "ws://localhost:8000/ws/job"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"command": "start"}))

        pbar = None
        try:
            while True:
                raw = await ws.recv()
                data = json.loads(raw)

                if data.get("type") == "ack":
                    print(data["message"])
                    pbar = tqdm(total=6, desc="Pipeline", unit="step")

                elif data.get("type") == "status":
                    if pbar:
                        pbar.set_description(data["message"][:40])
                        pbar.update(1)
                    if data.get("done"):
                        pbar.close()
                        print("\nJob finished.")
                        break

        except websockets.exceptions.ConnectionClosedOK:
            print("Connection closed cleanly.")


asyncio.run(run_job())
```

---

## 9. Case Study — AI Job Pipeline with Status Emitting

### Scenario

Drishya is building a resume screening system. HR uploads 50 resumes.
The system processes them with an NLP model and ranks candidates.
The frontend shows a live progress bar — no polling, pure WebSocket status stream.

### Architecture

```
                        ┌──────────────────────────────────────────────┐
                        │              FastAPI Server                   │
                        │                                              │
HR Frontend ──► POST /upload ──► store resumes in memory               │
            ──► WS /ws/pipeline/{job_id} ──► accept connection         │
                        │              │                               │
                        │              ├──► Phase 1: Load resumes      │
                        │              │    send status → client       │
                        │              ├──► Phase 2: Tokenize          │
                        │              │    send status → client       │
                        │              ├──► Phase 3: Model inference   │
                        │              │    send status → client       │
                        │              ├──► Phase 4: Rank results      │
                        │              │    send status → client       │
                        │              └──► Phase 5: Done              │
                        │                   send results → client      │
                        └──────────────────────────────────────────────┘
```

### Status message structure

Every status update follows this schema:

```json
{
  "job_id":   "abc123",
  "phase":    "inference",
  "step":     3,
  "total":    5,
  "percent":  60,
  "message":  "Running NLP model on 50 resumes...",
  "done":     false,
  "results":  null
}
```

Final message adds:

```json
{
  "job_id":   "abc123",
  "phase":    "complete",
  "step":     5,
  "total":    5,
  "percent":  100,
  "message":  "Screening complete. 50 resumes ranked.",
  "done":     true,
  "results":  [{"name": "Tanvi Joshi", "score": 0.94}, ...]
}
```

### `09_case_study_pipeline.py`

```python
# Case Study: AI Resume Screening Pipeline with WebSocket status emitting
# job_store: in-memory dict keyed by job_id holding resume lists
# run_pipeline: async generator that yields status dicts at each phase
# pipeline_endpoint: accepts ws, runs pipeline, streams status to client
# Phases: load, tokenize, inference, rank, done
# Precondition: POST /jobs/create called first to get job_id
# Time: O(n * phases) where n = resumes | Space: O(n) for resume store
# Dry run:
#   POST /jobs/create → job_id = "abc123"
#   WS connect /ws/pipeline/abc123 → accept
#   phase 1: load → send status(step=1, percent=20, done=False)
#   phase 2: tokenize → send status(step=2, percent=40, done=False)
#   phase 3: inference → send status(step=3, percent=60, done=False)
#   phase 4: rank → send status(step=4, percent=80, done=False)
#   phase 5: complete → send status(step=5, percent=100, done=True, results=[...])
#   connection closed gracefully

import asyncio
import uuid
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

# in-memory job store: job_id → list of candidate names
job_store: Dict[str, List[str]] = {}

CANDIDATES = [
    "Tanvi Joshi", "Arjun Mehta", "Priya Reddy", "Karan Sharma",
    "Meera Nair", "Rohit Verma", "Siddharth Iyer", "Pooja Patil",
    "Vikram Gupta", "Ananya Singh",
]


class JobRequest(BaseModel):
    resumes: List[str]


@app.post("/jobs/create")
async def create_job(request: JobRequest):
    job_id = str(uuid.uuid4())[:8]
    job_store[job_id] = request.resumes
    return {"job_id": job_id, "count": len(request.resumes)}


async def run_pipeline(job_id: str, resumes: List[str]):
    """Async generator that yields status dicts for each pipeline phase."""
    total_phases = 5
    n = len(resumes)

    # Phase 1: Load
    await asyncio.sleep(1.0)
    yield {
        "job_id": job_id, "phase": "load", "step": 1, "total": total_phases,
        "percent": 20, "message": f"Loaded {n} resumes from storage.", "done": False, "results": None
    }

    # Phase 2: Tokenize
    await asyncio.sleep(1.5)
    yield {
        "job_id": job_id, "phase": "tokenize", "step": 2, "total": total_phases,
        "percent": 40, "message": f"Tokenized {n} resumes with NLP pipeline.", "done": False, "results": None
    }

    # Phase 3: Inference
    await asyncio.sleep(2.0)
    yield {
        "job_id": job_id, "phase": "inference", "step": 3, "total": total_phases,
        "percent": 60, "message": f"Running model inference on {n} resumes...", "done": False, "results": None
    }

    # Phase 4: Rank
    await asyncio.sleep(1.0)
    yield {
        "job_id": job_id, "phase": "rank", "step": 4, "total": total_phases,
        "percent": 80, "message": "Ranking candidates by relevance score.", "done": False, "results": None
    }

    # Phase 5: Done — produce ranked results
    await asyncio.sleep(0.5)
    scored = [
        {"name": r, "score": round(random.uniform(0.60, 0.99), 2)}
        for r in resumes
    ]
    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)

    yield {
        "job_id": job_id, "phase": "complete", "step": 5, "total": total_phases,
        "percent": 100, "message": f"Screening complete. {n} resumes ranked.",
        "done": True, "results": ranked
    }


@app.websocket("/ws/pipeline/{job_id}")
async def pipeline_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()

    if job_id not in job_store:
        await websocket.send_json({"error": f"Job '{job_id}' not found."})
        await websocket.close(code=1008)
        return

    resumes = job_store[job_id]

    try:
        async for status in run_pipeline(job_id, resumes):
            await websocket.send_json(status)

        await websocket.close(code=1000)

    except WebSocketDisconnect:
        print(f"Client disconnected from job {job_id}")
```

### `09_test_pipeline.py`

```python
# Test the resume screening pipeline end-to-end
# Step 1: POST to create job and get job_id
# Step 2: Connect WebSocket and stream status updates
# Uses tqdm for live progress bar
# Precondition: case study server running on port 8000

import asyncio
import json
import httpx
import websockets
from tqdm import tqdm

BASE_URL  = "http://localhost:8000"
WS_URL    = "ws://localhost:8000"

RESUMES = [
    "Tanvi Joshi", "Arjun Mehta", "Priya Reddy", "Karan Sharma",
    "Meera Nair", "Rohit Verma", "Siddharth Iyer", "Pooja Patil",
    "Vikram Gupta", "Ananya Singh",
]


async def main():
    # Step 1: create job via REST
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/jobs/create", json={"resumes": RESUMES})
        job = resp.json()
        job_id = job["job_id"]
        print(f"Job created: {job_id} ({job['count']} resumes)\n")

    # Step 2: connect WebSocket and watch pipeline
    uri = f"{WS_URL}/ws/pipeline/{job_id}"
    async with websockets.connect(uri) as ws:
        pbar = tqdm(total=100, desc="Pipeline", unit="%", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}%")

        try:
            prev_percent = 0
            while True:
                raw = await ws.recv()
                data = json.loads(raw)

                if "error" in data:
                    print(f"Error: {data['error']}")
                    break

                # update progress bar
                delta = data["percent"] - prev_percent
                pbar.update(delta)
                prev_percent = data["percent"]
                pbar.set_description(f"[{data['phase'].upper()}] {data['message'][:40]}")

                if data["done"]:
                    pbar.close()
                    print("\nTop Candidates:")
                    print("-" * 35)
                    for i, c in enumerate(data["results"][:5], 1):
                        print(f"  {i}. {c['name']:<20} score: {c['score']}")
                    break

        except websockets.exceptions.ConnectionClosedOK:
            pbar.close()
            print("\nPipeline complete.")


asyncio.run(main())
```

### Expected output

```
Job created: f3a91b2c (10 resumes)

Pipeline:  20%|████      | 20/100%  [LOAD] Loaded 10 resumes from storage.
Pipeline:  40%|████████  | 40/100%  [TOKENIZE] Tokenized 10 resumes with NLP pipeline.
Pipeline:  60%|████████████| 60/100% [INFERENCE] Running model inference on 10 resumes...
Pipeline:  80%|████████████████| 80/100% [RANK] Ranking candidates by relevance score.
Pipeline: 100%|████████████████████|100/100% [COMPLETE] Screening complete. 10 resumes ranked.

Top Candidates:
-----------------------------------
  1. Tanvi Joshi           score: 0.97
  2. Vikram Gupta          score: 0.94
  3. Priya Reddy           score: 0.91
  4. Arjun Mehta           score: 0.88
  5. Siddharth Iyer        score: 0.84
```

---

## 10. Testing WebSocket Endpoints

### Option A — Python `websockets` library (used throughout these notes)

```bash
pip install websockets httpx
python 09_test_pipeline.py
```

### Option B — `websocat` CLI tool (best for quick manual testing)

```bash
# install
brew install websocat           # macOS
cargo install websocat          # Linux (Rust)

# connect and send messages manually
websocat ws://localhost:8000/ws

# connect with a named path param
websocat ws://localhost:8000/ws/Rohit
```

### Option C — FastAPI TestClient (for unit tests with pytest)

```python
# test_websocket_pytest.py
# FastAPI's TestClient supports WebSocket testing without running a live server
# with client.websocket_connect: opens a test WebSocket connection
# ws.send_text / ws.receive_text: synchronous in test context
# Precondition: pytest and httpx installed

from fastapi.testclient import TestClient
from fastapi import FastAPI, WebSocket

app = FastAPI()


@app.websocket("/ws")
async def echo(ws: WebSocket):
    await ws.accept()
    data = await ws.receive_text()
    await ws.send_text(f"Echo: {data}")


def test_echo():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("Hello Meera")
        response = ws.receive_text()
        assert response == "Echo: Hello Meera"
        print("Test passed:", response)
```

Run:

```bash
pip install pytest
pytest test_websocket_pytest.py -v
```

### Option D — Browser DevTools

1. Open browser → DevTools → Console
2. Paste:

```javascript
const ws = new WebSocket("ws://localhost:8000/ws");
ws.onopen = () => { console.log("Connected"); ws.send("Hello from browser"); };
ws.onmessage = (e) => console.log("Server:", e.data);
ws.onclose = (e) => console.log("Closed:", e.code, e.reason);
```

---

## 11. Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `RuntimeError: Expected ASGI message 'websocket.send'` | Called `send` before `accept()` | Always call `await websocket.accept()` first |
| `1006 Abnormal Closure` | Network dropped, no close handshake | Add reconnect logic in client; add heartbeat on server |
| `WebSocketDisconnect` not caught | Client closed tab unexpectedly | Always wrap the receive loop in `try/except WebSocketDisconnect` |
| `json.JSONDecodeError` | Client sent malformed JSON | Wrap `json.loads` in try/except, send error back |
| `broadcast` crashes for one client | One connection died mid-loop | Use `try/except` per connection inside broadcast |
| `ws://` blocked in production | Mixed content (HTTP page + ws://) | Use `wss://` for all production WebSocket URLs |
| Server sends to closed connection | Connection left stale in manager | Call `manager.disconnect(ws)` in the except block |

### Safe broadcast (handles individual connection failures)

```python
async def safe_broadcast(self, message: str):
    # try each connection individually so one dead socket doesn't kill others
    dead = []
    for conn in self.active_connections:
        try:
            await conn.send_text(message)
        except Exception:
            dead.append(conn)
    for conn in dead:
        self.active_connections.remove(conn)
```

---

## 12. Quick Reference Cheat Sheet

### FastAPI WebSocket API

```python
# Lifecycle
await websocket.accept()           # must call before anything else
await websocket.close(code=1000)   # close cleanly

# Receive
data = await websocket.receive_text()   # receive UTF-8 string
data = await websocket.receive_bytes()  # receive raw bytes
data = await websocket.receive_json()   # receive and parse JSON

# Send
await websocket.send_text("hello")      # send UTF-8 string
await websocket.send_bytes(b"\x00")     # send binary
await websocket.send_json({"key":"v"})  # serialize dict and send

# State
websocket.client_state   # WebSocketState enum
websocket.application_state
```

### Endpoint decorator

```python
@app.websocket("/ws/{param}")
async def handler(websocket: WebSocket, param: str):
    ...
```

### Connection lifecycle reminder

```
new WebSocket(url)
    → CONNECTING
    → accept() called
    → OPEN
    → send/receive frames
    → WebSocketDisconnect raised OR close() called
    → CLOSED
```

### Status emitting pattern (minimal template)

```python
@app.websocket("/ws/progress")
async def progress(ws: WebSocket):
    await ws.accept()
    steps = ["step1", "step2", "step3"]
    for i, step in enumerate(steps, 1):
        await ws.send_json({"step": i, "name": step, "done": i == len(steps)})
        await asyncio.sleep(1)
    await ws.close(1000)
```

### Decision flow

```
Need real-time?
  No  → HTTP REST
  Yes → Client needs to send data?
        No  → SSE (simpler)
        Yes → WebSocket
```

---

> **Next Step:** WebSocket authentication (token in query param or first message),
> Redis pub/sub for multi-server broadcast, and Nginx reverse proxy config for wss://.