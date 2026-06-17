# **SSE with Flask — Complete Notes From Basic to Advanced**

---

## **Table of Contents**

1. [Setup — Install everything you need](#1-setup--install-everything-you-need)
2. [Project structure we will build](#2-project-structure-we-will-build)
3. [Example 1 — Tiny SSE server (the smallest possible)](#3-example-1--tiny-sse-server-the-smallest-possible)
4. [Example 2 — HTML/JS test client](#4-example-2--htmljs-test-client)
5. [Example 3 — Named event types (custom channels)](#5-example-3--named-event-types-custom-channels)
6. [Example 4 — Event IDs and Last-Event-ID reconnect](#6-example-4--event-ids-and-last-event-id-reconnect)
7. [Example 5 — Multiple clients with a queue (no Redis)](#7-example-5--multiple-clients-with-a-queue-no-redis)
8. [Example 6 — Broadcast to all connected clients](#8-example-6--broadcast-to-all-connected-clients)
9. [Example 7 — Keepalive heartbeat (prevent proxy timeouts)](#9-example-7--keepalive-heartbeat-prevent-proxy-timeouts)
10. [Example 8 — Authentication with JWT (token in query param)](#10-example-8--authentication-with-jwt-token-in-query-param)
11. [Example 9 — Channels / topics (subscribe to specific streams)](#11-example-9--channels--topics-subscribe-to-specific-streams)
12. [Example 10 — Scaling with Redis Pub/Sub (multiple workers)](#12-example-10--scaling-with-redis-pubsub-multiple-workers)
13. [Example 11 — AI token streaming simulation](#13-example-11--ai-token-streaming-simulation)
14. [Example 12 — Background task with progress streaming](#14-example-12--background-task-with-progress-streaming)
15. [Case Study — Live notification system step by step](#15-case-study--live-notification-system-step-by-step)
16. [Testing your SSE server](#16-testing-your-sse-server)
17. [Common pitfalls in Flask SSE](#17-common-pitfalls-in-flask-sse)
18. [Quick reference card](#18-quick-reference-card)

---

## **1. Setup — Install everything you need**

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install the packages
pip install flask
pip install flask-cors           # For CORS (frontend on different port)
pip install pyjwt                # For JWT auth examples
pip install redis                # For Redis pub/sub scaling example

# For running with async workers (REQUIRED for SSE to work properly)
pip install gunicorn
pip install gevent               # Async worker for gunicorn

# Optional but useful
pip install python-dotenv        # Load .env config files
```

**Why gunicorn + gevent?**

Flask's built-in dev server handles ONE request at a time. SSE keeps a connection open forever, so the dev server gets stuck on that one SSE connection and cannot handle anything else. Gunicorn with gevent workers handles many connections at once using cooperative async.

```bash
# Run with gunicorn + gevent for SSE
gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:5000 app:app

# For development only (single client testing), flask dev server works but ONLY for testing
flask run
```

---

## **2. Project structure we will build**

```
sse_flask_project/
│
├── app.py                  ← main app
├── sse_helpers.py          ← helper functions (format events, etc.)
├── client_manager.py       ← tracks connected clients
├── requirements.txt
│
├── templates/
│   └── index.html          ← test HTML client
│
└── examples/
    ├── example1_basic.py
    ├── example5_queue.py
    ├── example10_redis.py
    └── example15_casestudy.py
```

---

## **3. Example 1 — Tiny SSE server (the smallest possible)**

This is the absolute minimum Flask SSE server. Read this first and understand it completely before moving forward.

**`example1_basic.py`**

```python
import time
from flask import Flask, Response

app = Flask(__name__)


# This is a generator function — it yields events one by one
# Flask keeps the connection open as long as this generator keeps running
def event_stream():
    count = 0
    while True:
        count += 1
        # SSE format: "data: <your message>\n\n"
        # The double \n\n marks the end of one event
        yield f"data: Message number {count}\n\n"
        time.sleep(1)  # wait 1 second before next event


@app.route("/events")
def sse_endpoint():
    # Response with mimetype text/event-stream tells browser "this is SSE"
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/")
def index():
    return "<h1>SSE Test</h1><p>Open /events in browser or connect EventSource</p>"


if __name__ == "__main__":
    # flask dev server — ok for single client testing only
    app.run(debug=True, threaded=True)
```

**What is happening here:**

```
Browser                          Flask
  |                                |
  |--- GET /events --------------->|
  |                                | ← generator starts running
  |<-- HTTP 200 ------------------|
  |<-- Content-Type: text/event-stream
  |                                |
  |<-- data: Message number 1\n\n |  ← after 1 second
  |<-- data: Message number 2\n\n |  ← after 2 seconds
  |<-- data: Message number 3\n\n |  ← after 3 seconds
  |   (connection stays open)      |
```

**Run it:**
```bash
python example1_basic.py
```

Open `http://localhost:5000/events` in your browser — you will see a stream of text appearing every second.

---

## **4. Example 2 — HTML/JS test client**

```python
# app.py — server with HTML client built in
import time
import json
from flask import Flask, Response

app = Flask(__name__)


def event_stream():
    count = 0
    while True:
        count += 1
        message = {"count": count, "message": f"Hello number {count}"}
        # Send JSON as the data value
        yield f"data: {json.dumps(message)}\n\n"
        time.sleep(2)


@app.route("/events")
def sse():
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/")
def index():
    # Inline HTML so you don't need a separate file
    return """
<!DOCTYPE html>
<html>
<head>
    <title>SSE Test</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        #status { color: green; font-weight: bold; }
        #messages { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: auto; }
        .msg { margin: 5px 0; padding: 5px; background: #f0f0f0; }
    </style>
</head>
<body>
    <h1>SSE Live Updates</h1>
    <p>Status: <span id="status">Connecting...</span></p>
    <div id="messages"></div>
    <button onclick="stopStream()">Stop</button>

    <script>
        // Create the EventSource — this opens the SSE connection
        const eventSource = new EventSource('/events');
        const messagesDiv = document.getElementById('messages');
        const statusSpan = document.getElementById('status');

        // Fires when connection opens
        eventSource.onopen = function() {
            statusSpan.textContent = '🟢 Connected';
            statusSpan.style.color = 'green';
        };

        // Fires on every event from server
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const div = document.createElement('div');
            div.className = 'msg';
            div.textContent = `Count: ${data.count} | ${data.message}`;
            messagesDiv.prepend(div);  // Add at top
        };

        // Fires on error (connection drop, etc.)
        eventSource.onerror = function() {
            statusSpan.textContent = '🔴 Reconnecting...';
            statusSpan.style.color = 'red';
        };

        function stopStream() {
            eventSource.close();  // Permanently close the connection
            statusSpan.textContent = '⚫ Stopped';
            statusSpan.style.color = 'gray';
        }
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

---

## **5. Example 3 — Named event types (custom channels)**

So far all events use the default `message` type. With named events, you can have different event types and listen to each separately on the client.

**Server:**
```python
import time
import json
from flask import Flask, Response

app = Flask(__name__)


def event_stream():
    count = 0
    while True:
        count += 1

        # event: <name> sets the event type
        # client listens with: eventSource.addEventListener('<name>', ...)

        if count % 3 == 0:
            # Every 3rd event: send a notification
            yield (
                f"event: notification\n"
                f"data: {json.dumps({'text': 'New message arrived!'})}\n\n"
            )
        elif count % 2 == 0:
            # Every 2nd event: send a price update
            yield (
                f"event: price-update\n"
                f"data: {json.dumps({'symbol': 'BTC', 'price': 45000 + count * 10})}\n\n"
            )
        else:
            # All others: send a plain message (no event: field = default type)
            yield f"data: {json.dumps({'count': count})}\n\n"

        time.sleep(1)


@app.route("/events")
def sse():
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>Named Events Demo</h1>
<div id="log" style="font-family:monospace; white-space:pre; border:1px solid #ccc; padding:10px; height:300px; overflow:auto;"></div>

<script>
    const es = new EventSource('/events');
    const log = document.getElementById('log');

    function addLog(type, data) {
        log.textContent = `[${type}] ${JSON.stringify(data)}\n` + log.textContent;
    }

    // Default handler — catches events WITHOUT an event: field
    es.onmessage = function(e) {
        addLog('message', JSON.parse(e.data));
    };

    // Named event listeners — only fires for event: notification
    es.addEventListener('notification', function(e) {
        addLog('NOTIFICATION', JSON.parse(e.data));
    });

    // Named event listeners — only fires for event: price-update
    es.addEventListener('price-update', function(e) {
        addLog('PRICE', JSON.parse(e.data));
    });
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**What the server sends:**
```
data: {"count": 1}

event: price-update
data: {"symbol": "BTC", "price": 45020}

event: notification
data: {"text": "New message arrived!"}

data: {"count": 4}
```

---

## **6. Example 4 — Event IDs and Last-Event-ID reconnect**

This is how you make SSE reliable — no missed events on disconnect.

```python
import time
import json
from flask import Flask, Response, request

app = Flask(__name__)

# Simulated event store — in real app this would be a database
EVENT_STORE = []
for i in range(1, 20):
    EVENT_STORE.append({"id": i, "message": f"Stored event {i}", "timestamp": i * 100})


def event_stream_with_id():
    """
    Generator that:
    1. First sends any missed events (based on Last-Event-ID header)
    2. Then keeps sending new events
    """
    # Check if client is reconnecting and has a Last-Event-ID
    last_id = request.headers.get("Last-Event-ID")

    if last_id:
        # Client reconnected — send all events it missed
        last_id = int(last_id)
        missed = [e for e in EVENT_STORE if e["id"] > last_id]
        print(f"Client reconnected with Last-Event-ID: {last_id}, sending {len(missed)} missed events")
        for event in missed:
            yield (
                f"id: {event['id']}\n"
                f"data: {json.dumps(event)}\n\n"
            )
    else:
        # New client — send last 5 events as history
        for event in EVENT_STORE[-5:]:
            yield (
                f"id: {event['id']}\n"
                f"data: {json.dumps(event)}\n\n"
            )

    # Now stream new events
    current_id = len(EVENT_STORE)
    while True:
        current_id += 1
        new_event = {
            "id": current_id,
            "message": f"Live event {current_id}",
            "timestamp": int(time.time())
        }
        EVENT_STORE.append(new_event)

        # id: field — browser remembers this and sends it back on reconnect
        yield (
            f"id: {new_event['id']}\n"
            f"data: {json.dumps(new_event)}\n\n"
        )
        time.sleep(2)


@app.route("/events")
def sse():
    return Response(event_stream_with_id(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**What happens on reconnect:**

```
--- First connection ---
Client: GET /events
Server: id: 15 / data: stored event 15
Server: id: 16 / data: stored event 16
Server: id: 17 / data: live event 17

--- Network drops ---

--- Reconnect ---
Client: GET /events (Last-Event-ID: 17)
Server: sends events 18, 19, 20... (nothing missed!)
```

---

## **7. Example 5 — Multiple clients with a queue (no Redis)**

The problem: if you have multiple clients connected, how do you send data to ALL of them? You need a way for each client to have its own stream.

This example uses Python's built-in `queue.Queue` — one queue per client. No Redis needed. Good for single-server deployments.

```python
import time
import json
import queue
import threading
from flask import Flask, Response, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

# This dict holds one queue per connected client
# Key: client_id, Value: queue.Queue
clients = {}
clients_lock = threading.Lock()  # Protect the dict from race conditions


def add_client(client_id):
    """Add a new client and give them a queue"""
    q = queue.Queue(maxsize=100)  # Max 100 buffered messages per client
    with clients_lock:
        clients[client_id] = q
    return q


def remove_client(client_id):
    """Remove a client when they disconnect"""
    with clients_lock:
        clients.pop(client_id, None)
    print(f"Client {client_id} disconnected. Total clients: {len(clients)}")


def broadcast(message, event_type="message"):
    """Put a message into every connected client's queue"""
    data = json.dumps(message)
    dead_clients = []

    with clients_lock:
        for client_id, q in clients.items():
            try:
                q.put_nowait(f"event: {event_type}\ndata: {data}\n\n")
            except queue.Full:
                # Client's queue is full — they are probably disconnected
                dead_clients.append(client_id)

    # Clean up dead clients outside the lock
    for client_id in dead_clients:
        remove_client(client_id)


def stream_from_queue(client_id, client_queue):
    """Generator that reads from a client's queue and yields events"""
    try:
        while True:
            try:
                # Wait up to 20 seconds for a message
                # If nothing arrives in 20s, send a keepalive comment
                message = client_queue.get(timeout=20)
                yield message
            except queue.Empty:
                # Send a comment as keepalive — browser ignores it but connection stays alive
                yield ": keepalive\n\n"
    except GeneratorExit:
        # Client disconnected
        remove_client(client_id)


@app.route("/events")
def sse():
    # Give each client a unique ID
    client_id = request.args.get("client_id", f"client_{id(request)}")
    print(f"New client: {client_id}. Total clients: {len(clients) + 1}")

    client_queue = add_client(client_id)

    # Send a welcome event immediately
    client_queue.put(f"event: connected\ndata: {json.dumps({'client_id': client_id})}\n\n")

    return Response(
        stream_from_queue(client_id, client_queue),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.route("/broadcast", methods=["POST"])
def trigger_broadcast():
    """API endpoint to trigger a broadcast to all clients"""
    data = request.json or {}
    message = data.get("message", "Hello everyone!")
    broadcast({"text": message, "timestamp": time.time()}, event_type="announcement")
    return {"status": "ok", "clients": len(clients)}


@app.route("/status")
def status():
    return {"connected_clients": len(clients), "client_ids": list(clients.keys())}


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**Test it:**
```bash
# Connect two clients
curl -N http://localhost:5000/events?client_id=user1 &
curl -N http://localhost:5000/events?client_id=user2 &

# Broadcast to both
curl -X POST http://localhost:5000/broadcast \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello everyone!"}'
```

---

## **8. Example 6 — Broadcast to all connected clients**

Build on Example 5 but add a proper broadcaster class that is cleaner and reusable.

```python
import time
import json
import queue
import threading
import uuid
from flask import Flask, Response, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


class SSEBroadcaster:
    """
    Manages all SSE client connections.
    Each client gets their own queue.
    Broadcast puts a message in every queue.
    """

    def __init__(self):
        self.clients = {}   # {client_id: queue.Queue}
        self.lock = threading.Lock()

    def connect(self, client_id=None):
        """Register a new client. Returns (client_id, queue)"""
        if client_id is None:
            client_id = str(uuid.uuid4())[:8]
        q = queue.Queue(maxsize=50)
        with self.lock:
            self.clients[client_id] = q
        print(f"[+] Client {client_id} connected. Total: {len(self.clients)}")
        return client_id, q

    def disconnect(self, client_id):
        """Remove a client"""
        with self.lock:
            self.clients.pop(client_id, None)
        print(f"[-] Client {client_id} disconnected. Total: {len(self.clients)}")

    def broadcast(self, data, event_type="message", event_id=None):
        """Send an event to ALL connected clients"""
        lines = []
        if event_id:
            lines.append(f"id: {event_id}")
        lines.append(f"event: {event_type}")
        lines.append(f"data: {json.dumps(data)}")
        message = "\n".join(lines) + "\n\n"

        dead = []
        with self.lock:
            for cid, q in self.clients.items():
                try:
                    q.put_nowait(message)
                except queue.Full:
                    dead.append(cid)

        for cid in dead:
            self.disconnect(cid)

    def send_to(self, client_id, data, event_type="message"):
        """Send an event to ONE specific client"""
        with self.lock:
            q = self.clients.get(client_id)
        if q:
            message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            try:
                q.put_nowait(message)
                return True
            except queue.Full:
                return False
        return False

    def count(self):
        return len(self.clients)

    def stream(self, client_id, q):
        """Generator for a specific client"""
        try:
            while True:
                try:
                    yield q.get(timeout=15)
                except queue.Empty:
                    yield ": ping\n\n"  # keepalive
        except GeneratorExit:
            self.disconnect(client_id)


# One global broadcaster instance
broadcaster = SSEBroadcaster()


@app.route("/events")
def sse():
    client_id, q = broadcaster.connect()
    # Send initial welcome
    welcome = f"event: welcome\ndata: {json.dumps({'id': client_id, 'msg': 'Connected!'})}\n\n"
    q.put(welcome)
    return Response(
        broadcaster.stream(client_id, q),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/broadcast", methods=["POST"])
def do_broadcast():
    data = request.json or {}
    broadcaster.broadcast(
        data={"text": data.get("text", ""), "ts": time.time()},
        event_type=data.get("event_type", "message")
    )
    return {"ok": True, "sent_to": broadcaster.count()}


@app.route("/send/<client_id>", methods=["POST"])
def send_to_client(client_id):
    data = request.json or {}
    ok = broadcaster.send_to(client_id, data, event_type="direct-message")
    return {"ok": ok}


@app.route("/clients")
def list_clients():
    return {"count": broadcaster.count(), "ids": list(broadcaster.clients.keys())}


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

---

## **9. Example 7 — Keepalive heartbeat (prevent proxy timeouts)**

Most load balancers and proxies (nginx, AWS ALB, Cloudflare) close idle connections after 30-60 seconds. SSE connections look idle when no events are being sent. A keepalive comment prevents this.

```python
import time
import json
import queue
import threading
from flask import Flask, Response

app = Flask(__name__)


def event_stream_with_heartbeat():
    """
    Generator that sends real events AND keepalive pings.
    Keepalive format: ": ping\n\n"
    Starts with colon = comment line, browser ignores it but connection stays alive.
    """
    last_event_time = time.time()
    event_count = 0

    while True:
        now = time.time()
        time_since_last = now - last_event_time

        # Only have a real event every 10 seconds (simulating rare events)
        if time_since_last >= 10:
            event_count += 1
            data = {"event_count": event_count, "message": "Real event!"}
            yield f"event: update\ndata: {json.dumps(data)}\n\n"
            last_event_time = now

        else:
            # Send a keepalive comment every 15 seconds
            # Lines starting with : are comments — browser ignores but keeps connection open
            yield ": keepalive\n\n"

        time.sleep(15)  # Check every 15 seconds


@app.route("/events")
def sse():
    return Response(
        event_stream_with_heartbeat(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # nginx: don't buffer
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**Nginx config for SSE (no buffering):**
```nginx
location /events {
    proxy_pass http://localhost:5000;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;           # Critical — disable buffering
    proxy_cache off;
    proxy_read_timeout 86400s;     # 24 hours timeout (long-lived connection)
    chunked_transfer_encoding on;
}
```

---

## **10. Example 8 — Authentication with JWT (token in query param)**

`EventSource` in the browser does not support custom headers. So we pass the JWT token as a query parameter and validate it on the server.

```python
import time
import json
import jwt  # pip install pyjwt
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, Response, request, jsonify

app = Flask(__name__)
SECRET_KEY = "your-secret-key-change-this"


# ─── Auth helpers ────────────────────────────────────────────────────────────

def generate_token(user_id, username):
    """Create a JWT token for a user"""
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=1)  # Expires in 1 hour
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def validate_token(token):
    """Validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Bad token


def sse_auth_required(f):
    """Decorator — validates token from query param before running the route"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get("token")
        if not token:
            return Response("Missing token", status=401)
        user = validate_token(token)
        if not user:
            return Response("Invalid or expired token", status=401)
        # Attach user info to request context so the route can use it
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/login", methods=["POST"])
def login():
    """Return a JWT token for testing"""
    data = request.json or {}
    username = data.get("username", "testuser")
    token = generate_token(user_id=1, username=username)
    return jsonify({"token": token, "username": username})


@app.route("/events")
@sse_auth_required  # Validates token before anything runs
def sse():
    user = request.current_user
    print(f"SSE connected: {user['username']}")

    def generate():
        count = 0
        while True:
            count += 1
            data = {
                "count": count,
                "user": user["username"],
                "message": f"Hello {user['username']}, event #{count}"
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(2)

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**Client-side usage:**
```javascript
// Step 1: Login to get token
const loginRes = await fetch('/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: 'ali'})
});
const {token} = await loginRes.json();

// Step 2: Connect SSE with token in query param
const es = new EventSource(`/events?token=${token}`);

es.onmessage = (e) => console.log(JSON.parse(e.data));
es.onerror   = (e) => console.log('Error or reconnecting');
```

**Test with curl:**
```bash
# Get a token
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"ali"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Connect SSE with token
curl -N "http://localhost:5000/events?token=$TOKEN"
```

---

## **11. Example 9 — Channels / topics (subscribe to specific streams)**

Instead of one stream for everything, let clients subscribe to specific channels. Example: users subscribe to `channel=orders`, `channel=notifications`, `channel=analytics` separately.

```python
import time
import json
import queue
import threading
from flask import Flask, Response, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


class ChannelManager:
    """
    Manages clients per channel.
    channel_clients = {
      "orders":        {client_id: queue, ...},
      "notifications": {client_id: queue, ...},
      "analytics":     {client_id: queue, ...},
    }
    """

    def __init__(self):
        self.channel_clients = {}
        self.lock = threading.Lock()

    def subscribe(self, channel, client_id):
        """Subscribe a client to a channel"""
        q = queue.Queue(maxsize=50)
        with self.lock:
            if channel not in self.channel_clients:
                self.channel_clients[channel] = {}
            self.channel_clients[channel][client_id] = q
        print(f"[+] {client_id} subscribed to '{channel}'")
        return q

    def unsubscribe(self, channel, client_id):
        """Remove a client from a channel"""
        with self.lock:
            ch = self.channel_clients.get(channel, {})
            ch.pop(client_id, None)
        print(f"[-] {client_id} left '{channel}'")

    def publish(self, channel, data, event_type="message"):
        """Send an event to all clients in a channel"""
        message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        dead = []
        with self.lock:
            clients_in_channel = dict(self.channel_clients.get(channel, {}))

        for cid, q in clients_in_channel.items():
            try:
                q.put_nowait(message)
            except queue.Full:
                dead.append((channel, cid))

        for (ch, cid) in dead:
            self.unsubscribe(ch, cid)

    def subscriber_count(self, channel):
        with self.lock:
            return len(self.channel_clients.get(channel, {}))

    def stream(self, channel, client_id, q):
        """Generator for a client in a channel"""
        try:
            while True:
                try:
                    yield q.get(timeout=20)
                except queue.Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            self.unsubscribe(channel, client_id)


manager = ChannelManager()


@app.route("/events/<channel>")
def sse(channel):
    """
    Connect to a specific channel:
    GET /events/orders
    GET /events/notifications
    GET /events/analytics
    """
    ALLOWED_CHANNELS = {"orders", "notifications", "analytics", "general"}
    if channel not in ALLOWED_CHANNELS:
        return {"error": "Unknown channel"}, 400

    client_id = request.args.get("client_id", f"anon_{id(request)}")
    q = manager.subscribe(channel, client_id)

    # Send confirmation
    q.put(f"event: subscribed\ndata: {json.dumps({'channel': channel, 'client': client_id})}\n\n")

    return Response(
        manager.stream(channel, client_id, q),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/publish/<channel>", methods=["POST"])
def publish(channel):
    """Publish an event to a channel"""
    data = request.json or {}
    manager.publish(channel, data, event_type=data.pop("event_type", "message"))
    return {"ok": True, "subscribers": manager.subscriber_count(channel)}


@app.route("/channels")
def channels_status():
    status = {}
    for ch in ["orders", "notifications", "analytics", "general"]:
        status[ch] = manager.subscriber_count(ch)
    return status


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**Test with curl:**
```bash
# Subscribe to orders channel
curl -N "http://localhost:5000/events/orders?client_id=user1" &

# Publish to orders channel
curl -X POST http://localhost:5000/publish/orders \
  -H "Content-Type: application/json" \
  -d '{"event_type": "order-created", "order_id": "ORD001", "amount": 1500}'
```

---

## **12. Example 10 — Scaling with Redis Pub/Sub (multiple workers)**

**The problem with in-memory queues:**

When you run 2+ gunicorn workers, each worker has its own memory. If client A is on worker 1 and you call `/broadcast` on worker 2, worker 2's in-memory dict does not know about client A. The broadcast fails for some clients.

**The solution:** Redis Pub/Sub. Every worker subscribes to Redis. When any worker publishes, Redis delivers to ALL workers, which then forward to their local clients.

```
Worker 1            Worker 2
  Client A            Client B
      \                  /
       Redis Pub/Sub ←──── POST /broadcast
         ↓
    All workers get it → forward to their local clients
```

```python
import time
import json
import queue
import threading
import redis
from flask import Flask, Response, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Connect to Redis
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


class RedisSSEManager:
    """
    Each worker process runs one instance.
    Publishes go through Redis to reach ALL workers.
    Each worker keeps its own local client queues.
    """

    def __init__(self):
        self.local_clients = {}   # Local clients on THIS worker
        self.lock = threading.Lock()
        self._start_redis_listener()

    def _start_redis_listener(self):
        """Start a background thread that listens to Redis and forwards to local clients"""
        def listen():
            pubsub = redis_client.pubsub()
            pubsub.subscribe("sse_events")  # Subscribe to the Redis channel
            print("Redis listener started")
            for redis_message in pubsub.listen():
                if redis_message["type"] == "message":
                    # Forward the message to all local clients
                    self._forward_to_local_clients(redis_message["data"])

        t = threading.Thread(target=listen, daemon=True)
        t.start()

    def _forward_to_local_clients(self, raw_message):
        """Send a raw SSE string to all local clients"""
        dead = []
        with self.lock:
            for cid, q in self.local_clients.items():
                try:
                    q.put_nowait(raw_message)
                except queue.Full:
                    dead.append(cid)
        for cid in dead:
            self.remove_client(cid)

    def add_client(self, client_id):
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.local_clients[client_id] = q
        return q

    def remove_client(self, client_id):
        with self.lock:
            self.local_clients.pop(client_id, None)

    def publish(self, data, event_type="message", event_id=None):
        """
        Publish to Redis — ALL workers will receive and forward to their clients.
        """
        lines = []
        if event_id:
            lines.append(f"id: {event_id}")
        lines.append(f"event: {event_type}")
        lines.append(f"data: {json.dumps(data)}")
        sse_message = "\n".join(lines) + "\n\n"

        # Publish to Redis — every worker's listener will pick this up
        redis_client.publish("sse_events", sse_message)

    def stream(self, client_id, q):
        try:
            while True:
                try:
                    yield q.get(timeout=20)
                except queue.Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            self.remove_client(client_id)


manager = RedisSSEManager()


@app.route("/events")
def sse():
    client_id = request.args.get("client_id", f"c_{id(request)}")
    q = manager.add_client(client_id)
    q.put(f"event: connected\ndata: {json.dumps({'id': client_id})}\n\n")
    return Response(
        manager.stream(client_id, q),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/publish", methods=["POST"])
def publish():
    data = request.json or {}
    event_id = int(time.time() * 1000)
    manager.publish(
        data=data,
        event_type=data.pop("event_type", "message"),
        event_id=event_id
    )
    return {"ok": True}


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**Run with 2 workers:**
```bash
gunicorn --worker-class gevent --workers 2 --bind 0.0.0.0:5000 app:app
```

Now broadcasts reach clients connected to ANY worker.

---

## **13. Example 11 — AI token streaming simulation**

This is how ChatGPT/Claude-style streaming works. Server sends tokens one by one. Client shows them progressively.

```python
import time
import json
from flask import Flask, Response, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Fake AI responses for demo (replace with real LLM call)
FAKE_RESPONSES = {
    "weather": "The weather today is looking quite nice. Temperatures will be around 25°C with light clouds and a gentle breeze from the southwest.",
    "python": "Python is a high-level programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991.",
    "default": "I am an AI assistant. I can help you with many things. Just ask me a question and I will do my best to answer it clearly and concisely."
}


def tokenize(text):
    """Split text into word-by-word tokens (simulating LLM token streaming)"""
    words = text.split(" ")
    tokens = []
    for word in words:
        tokens.append(word + " ")
    return tokens


def stream_response(question):
    """
    Generator that streams an AI response token by token.
    This simulates how OpenAI/Claude streaming APIs work.
    """
    # Pick response based on keywords in question
    question_lower = question.lower()
    if "weather" in question_lower:
        response_text = FAKE_RESPONSES["weather"]
    elif "python" in question_lower:
        response_text = FAKE_RESPONSES["python"]
    else:
        response_text = FAKE_RESPONSES["default"]

    tokens = tokenize(response_text)
    token_index = 0

    # Send "thinking" signal first
    yield f"event: thinking\ndata: {json.dumps({'status': 'thinking'})}\n\n"
    time.sleep(0.5)

    # Stream tokens one by one
    for token in tokens:
        token_index += 1
        payload = {
            "token": token,
            "index": token_index,
            "done": False
        }
        yield f"event: token\ndata: {json.dumps(payload)}\n\n"
        time.sleep(0.05)  # Small delay between tokens — feels natural

    # Send "done" signal
    yield f"event: done\ndata: {json.dumps({'total_tokens': token_index, 'done': True})}\n\n"


@app.route("/chat/stream")
def chat_stream():
    """
    GET /chat/stream?question=what+is+python
    Returns an SSE stream of tokens
    """
    question = request.args.get("question", "tell me something")
    return Response(
        stream_response(question),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>AI Chat Streaming Demo</h1>
<input id="question" value="What is Python?" style="width:400px; padding:8px">
<button onclick="ask()">Ask</button>
<div id="answer" style="margin-top:20px; padding:15px; border:1px solid #ccc; min-height:100px; font-size:18px; white-space:pre-wrap;"></div>
<p id="status"></p>

<script>
let currentES = null;

function ask() {
    const question = document.getElementById('question').value;
    const answer = document.getElementById('answer');
    const status = document.getElementById('status');

    // Close previous stream if exists
    if (currentES) currentES.close();

    answer.textContent = '';
    status.textContent = '⏳ Thinking...';

    // Open SSE stream for this question
    currentES = new EventSource('/chat/stream?question=' + encodeURIComponent(question));

    currentES.addEventListener('thinking', () => {
        status.textContent = '⏳ AI is thinking...';
    });

    // Append each token to the answer div
    currentES.addEventListener('token', (e) => {
        const data = JSON.parse(e.data);
        answer.textContent += data.token;
        status.textContent = `📝 Streaming... (token ${data.index})`;
    });

    currentES.addEventListener('done', (e) => {
        const data = JSON.parse(e.data);
        status.textContent = `✅ Done! Total tokens: ${data.total_tokens}`;
        currentES.close();
    });

    currentES.onerror = () => {
        status.textContent = '❌ Error';
        currentES.close();
    };
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

---

## **14. Example 12 — Background task with progress streaming**

A common pattern: user triggers a long task (file processing, report generation, ML training), and wants to see live progress updates.

```python
import time
import json
import uuid
import queue
import threading
from flask import Flask, Response, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# job_id -> queue for that job's progress updates
job_queues = {}
job_lock = threading.Lock()


def run_long_task(job_id, task_name, total_steps):
    """
    Simulates a long background task.
    Sends progress events to the job's queue.
    """
    q = job_queues.get(job_id)
    if not q:
        return

    def send(event_type, data):
        q.put(f"event: {event_type}\ndata: {json.dumps(data)}\n\n")

    try:
        send("started", {"job_id": job_id, "task": task_name, "total": total_steps})

        for step in range(1, total_steps + 1):
            # Simulate work
            time.sleep(0.5)

            progress = int((step / total_steps) * 100)
            send("progress", {
                "step": step,
                "total": total_steps,
                "percent": progress,
                "message": f"Processing step {step} of {total_steps}..."
            })

        # Done
        send("completed", {
            "job_id": job_id,
            "message": f"Task '{task_name}' finished!",
            "result": {"processed": total_steps, "success": True}
        })

    except Exception as e:
        send("error", {"job_id": job_id, "error": str(e)})

    finally:
        # Clean up after 60 seconds
        def cleanup():
            time.sleep(60)
            with job_lock:
                job_queues.pop(job_id, None)
        threading.Thread(target=cleanup, daemon=True).start()


@app.route("/tasks/start", methods=["POST"])
def start_task():
    """Start a background task and return a job_id"""
    data = request.json or {}
    job_id = str(uuid.uuid4())[:8]
    task_name = data.get("task_name", "default_task")
    steps = data.get("steps", 10)

    # Create the progress queue for this job
    q = queue.Queue(maxsize=100)
    with job_lock:
        job_queues[job_id] = q

    # Start the task in a background thread
    t = threading.Thread(target=run_long_task, args=(job_id, task_name, steps), daemon=True)
    t.start()

    return jsonify({"job_id": job_id, "task_name": task_name})


@app.route("/tasks/<job_id>/progress")
def task_progress(job_id):
    """SSE endpoint to stream progress for a specific job"""
    with job_lock:
        q = job_queues.get(job_id)

    if not q:
        return Response(
            f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n",
            mimetype="text/event-stream",
            status=404
        )

    def generate():
        try:
            while True:
                try:
                    message = q.get(timeout=30)
                    yield message
                    # Stop streaming after 'completed' or 'error' event
                    if '"completed"' in message or '"error"' in message:
                        break
                except queue.Empty:
                    yield ": waiting\n\n"
        except GeneratorExit:
            pass

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>Background Task Progress Demo</h1>
<button onclick="startTask()">Start Task (10 steps)</button>
<div id="progress-bar" style="width:100%; background:#eee; margin:10px 0">
    <div id="bar" style="width:0%; height:20px; background:#4CAF50; transition:width 0.3s"></div>
</div>
<div id="log" style="font-family:monospace; border:1px solid #ccc; padding:10px; height:200px; overflow:auto"></div>

<script>
async function startTask() {
    const log = document.getElementById('log');
    const bar = document.getElementById('bar');
    log.innerHTML = '';
    bar.style.width = '0%';

    // 1. Start the task
    const res = await fetch('/tasks/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task_name: 'data_processing', steps: 10})
    });
    const {job_id} = await res.json();
    log.innerHTML = `Started job: ${job_id}<br>`;

    // 2. Connect SSE to track progress
    const es = new EventSource(`/tasks/${job_id}/progress`);

    es.addEventListener('started', (e) => {
        const d = JSON.parse(e.data);
        log.innerHTML += `✅ Task started: ${d.task}<br>`;
    });

    es.addEventListener('progress', (e) => {
        const d = JSON.parse(e.data);
        bar.style.width = d.percent + '%';
        log.innerHTML += `📊 ${d.percent}% - ${d.message}<br>`;
        log.scrollTop = log.scrollHeight;
    });

    es.addEventListener('completed', (e) => {
        const d = JSON.parse(e.data);
        bar.style.width = '100%';
        log.innerHTML += `🎉 ${d.message}<br>`;
        es.close();
    });

    es.addEventListener('error', (e) => {
        log.innerHTML += `❌ Error occurred<br>`;
        es.close();
    });
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

---

## **15. Case Study — Live notification system step by step**

**What we are building:** A notification system where:
- Users log in and get a JWT token
- Each user subscribes to their own notification stream
- Other users (or a backend service) can send notifications to specific users
- Notifications show instantly without polling

```
project/
├── app.py
├── auth.py
├── notifications.py
└── templates/dashboard.html
```

**`auth.py`**
```python
import jwt
from datetime import datetime, timedelta

SECRET = "notifications-secret-key"

def create_token(user_id, username):
    return jwt.encode(
        {"user_id": user_id, "username": username, "exp": datetime.utcnow() + timedelta(hours=8)},
        SECRET, algorithm="HS256"
    )

def decode_token(token):
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except:
        return None
```

**`notifications.py`**
```python
import json
import queue
import threading

class NotificationHub:
    """
    One queue per user.
    Anyone can push a notification to any user by user_id.
    """

    def __init__(self):
        self.user_queues = {}   # {user_id: queue.Queue}
        self.lock = threading.Lock()

    def subscribe(self, user_id):
        q = queue.Queue(maxsize=50)
        with self.lock:
            self.user_queues[user_id] = q
        print(f"User {user_id} subscribed")
        return q

    def unsubscribe(self, user_id):
        with self.lock:
            self.user_queues.pop(user_id, None)
        print(f"User {user_id} unsubscribed")

    def notify(self, user_id, notification_type, payload):
        """Send a notification to a specific user"""
        with self.lock:
            q = self.user_queues.get(user_id)
        if q:
            message = (
                f"event: {notification_type}\n"
                f"data: {json.dumps(payload)}\n\n"
            )
            try:
                q.put_nowait(message)
                return True
            except queue.Full:
                return False
        return False  # User not connected

    def broadcast(self, notification_type, payload):
        """Send a notification to ALL users"""
        count = 0
        with self.lock:
            user_ids = list(self.user_queues.keys())
        for uid in user_ids:
            if self.notify(uid, notification_type, payload):
                count += 1
        return count

    def stream(self, user_id, q):
        try:
            while True:
                try:
                    yield q.get(timeout=20)
                except queue.Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            self.unsubscribe(user_id)


hub = NotificationHub()
```

**`app.py`**
```python
import time
from flask import Flask, Response, request, jsonify, render_template_string
from flask_cors import CORS
from auth import create_token, decode_token
from notifications import hub

app = Flask(__name__)
CORS(app)

# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400

    # In a real app: check DB for user
    user_id = hash(username) % 10000  # Fake user ID
    token = create_token(user_id, username)
    return jsonify({"token": token, "user_id": user_id, "username": username})


# ─── SSE Notifications ────────────────────────────────────────────────────────

@app.route("/notifications/stream")
def notification_stream():
    """Connect to your personal notification stream"""
    token = request.args.get("token")
    if not token:
        return Response("Missing token", status=401)

    user = decode_token(token)
    if not user:
        return Response("Invalid token", status=401)

    user_id = user["user_id"]
    q = hub.subscribe(user_id)

    # Send initial "connected" event
    import json
    q.put(f"event: connected\ndata: {json.dumps({'user_id': user_id, 'username': user['username']})}\n\n")

    return Response(
        hub.stream(user_id, q),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ─── Send Notifications (API) ─────────────────────────────────────────────────

@app.route("/notifications/send/<int:user_id>", methods=["POST"])
def send_to_user(user_id):
    """Send a notification to a specific user"""
    data = request.json or {}
    notif_type = data.get("type", "info")
    payload = {
        "message": data.get("message", ""),
        "type": notif_type,
        "timestamp": time.time(),
        "from": data.get("from", "system")
    }
    delivered = hub.notify(user_id, notif_type, payload)
    return jsonify({"delivered": delivered, "user_id": user_id})


@app.route("/notifications/broadcast", methods=["POST"])
def broadcast():
    """Send a notification to all users"""
    data = request.json or {}
    count = hub.broadcast(
        notification_type=data.get("type", "announcement"),
        payload={
            "message": data.get("message", ""),
            "timestamp": time.time()
        }
    )
    return jsonify({"sent_to": count})


# ─── Dashboard UI ─────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Notification Dashboard</title>
<style>
  body { font-family: Arial; margin: 20px; max-width: 600px; }
  input { padding: 8px; width: 200px; }
  button { padding: 8px 16px; background: #007bff; color: white; border: none; cursor: pointer; }
  #notifications { margin-top: 20px; }
  .notif { padding: 10px; margin: 5px 0; border-left: 4px solid #007bff; background: #f8f9fa; }
  .notif.warning { border-color: orange; }
  .notif.error   { border-color: red; }
  #status { font-weight: bold; }
</style>
</head>
<body>
<h1>Live Notifications</h1>

<!-- Login -->
<div id="login-section">
  <input id="username" placeholder="Enter username">
  <button onclick="login()">Login & Connect</button>
</div>

<div id="app-section" style="display:none">
  <p>Status: <span id="status">Connecting...</span></p>
  <p>Your User ID: <span id="user-id-display"></span></p>
  <h3>Notifications:</h3>
  <div id="notifications"></div>
</div>

<script>
let token = null;
let userId = null;

async function login() {
    const username = document.getElementById('username').value;
    const res = await fetch('/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username})
    });
    const data = await res.json();
    token = data.token;
    userId = data.user_id;

    document.getElementById('login-section').style.display = 'none';
    document.getElementById('app-section').style.display = 'block';
    document.getElementById('user-id-display').textContent = userId;

    connectSSE();
}

function connectSSE() {
    const es = new EventSource(`/notifications/stream?token=${token}`);
    const status = document.getElementById('status');

    es.onopen = () => { status.textContent = '🟢 Connected'; };
    es.onerror = () => { status.textContent = '🔴 Reconnecting...'; };

    es.addEventListener('connected', (e) => {
        const d = JSON.parse(e.data);
        addNotification(`Welcome back, connected as user #${d.user_id}`, 'info');
    });

    // Listen for different notification types
    ['info', 'warning', 'error', 'announcement'].forEach(type => {
        es.addEventListener(type, (e) => {
            const d = JSON.parse(e.data);
            addNotification(d.message, type);
        });
    });
}

function addNotification(message, type='info') {
    const div = document.createElement('div');
    div.className = `notif ${type}`;
    div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    document.getElementById('notifications').prepend(div);
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
```

**Test sending notifications:**
```bash
# Send to user 1234
curl -X POST http://localhost:5000/notifications/send/1234 \
  -H "Content-Type: application/json" \
  -d '{"type": "warning", "message": "Your subscription expires in 3 days"}'

# Broadcast to everyone
curl -X POST http://localhost:5000/notifications/broadcast \
  -H "Content-Type: application/json" \
  -d '{"type": "announcement", "message": "System maintenance in 30 minutes"}'
```

---

## **16. Testing your SSE server**

### **Test with curl (best for quick checks)**
```bash
# Basic connection — -N disables buffering so you see events as they arrive
curl -N http://localhost:5000/events

# With headers
curl -N -H "Accept: text/event-stream" http://localhost:5000/events

# With auth token in query
curl -N "http://localhost:5000/events?token=your-jwt-token"

# See HTTP headers
curl -I http://localhost:5000/events
```

### **Test with Python requests (non-streaming)**
```python
import requests

# Stream SSE with requests
with requests.get("http://localhost:5000/events", stream=True) as r:
    print("Status:", r.status_code)
    print("Content-Type:", r.headers["content-type"])

    for line in r.iter_lines():
        if line:
            print("Line:", line.decode())
```

### **Test with Python httpx (better for SSE)**
```python
# pip install httpx
import httpx

with httpx.stream("GET", "http://localhost:5000/events") as r:
    for line in r.iter_lines():
        if line:
            print(line)
```

### **Test broadcast endpoint**
```bash
# Connect 2 clients
curl -N http://localhost:5000/events?client_id=c1 &
curl -N http://localhost:5000/events?client_id=c2 &

# Wait 2 seconds then broadcast
sleep 2
curl -X POST http://localhost:5000/broadcast \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello everyone!"}'
```

### **Check connected clients**
```bash
curl http://localhost:5000/clients
```

### **Test with pytest**
```python
import pytest
from app import app


@pytest.fixture
def client():
    app.testing = True
    with app.test_client() as c:
        yield c


def test_sse_headers(client):
    """SSE endpoint must return text/event-stream"""
    with client.get("/events", buffered=False) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.content_type


def test_sse_format(client):
    """Events must follow SSE format: data: ...\n\n"""
    with client.get("/events", buffered=False) as resp:
        # Read a few bytes to check format
        data = resp.data[:100].decode()
        # SSE data lines start with "data: "
        assert "data: " in data or ": " in data  # data or comment
```

---

## **17. Common pitfalls in Flask SSE**

### **Pitfall 1 — Flask dev server blocks on SSE (most common)**

**Problem:** You run `flask run`, open `/events`, and the app stops responding to all other requests.

**Why:** Flask dev server is single-threaded. It is stuck on the never-ending SSE response.

**Fix:**
```python
# Option A: Use threaded=True with dev server (ok for testing)
app.run(debug=True, threaded=True)

# Option B: Use gunicorn + gevent (correct for production)
# gunicorn --worker-class gevent --workers 1 app:app
```

---

### **Pitfall 2 — Events arrive as a big batch (buffering)**

**Problem:** You expect events one by one, but they all arrive at once after 10 seconds.

**Why:** nginx or another proxy is buffering the response.

**Fix:** Add these headers:
```python
return Response(
    generate(),
    mimetype="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",   # Tells nginx: don't buffer this
    }
)
```

And in nginx config:
```nginx
proxy_buffering off;
```

---

### **Pitfall 3 — stream_with_context needed for request-dependent generators**

**Problem:** You use `request.args` or `request.headers` inside your generator, and get "Working outside of request context" error.

**Why:** Flask clears the request context when the generator starts running outside the route.

**Fix:** Use `stream_with_context`:
```python
from flask import stream_with_context

@app.route("/events")
def sse():
    def generate():
        # Using request here would fail without stream_with_context
        user_id = request.args.get("user_id")   # ← This needs the request context
        while True:
            yield f"data: Hello user {user_id}\n\n"
            time.sleep(1)

    # Wrap the generator to keep request context alive
    return Response(
        stream_with_context(generate()),  # ← The fix
        mimetype="text/event-stream"
    )
```

---

### **Pitfall 4 — Disconnected clients not cleaned up**

**Problem:** Client closes browser. Server keeps sending events into a broken connection. Memory leaks grow.

**Fix:** Wrap generator in try/except GeneratorExit and clean up:
```python
def generate():
    client_id = register_client()
    try:
        while True:
            yield get_next_event()
    except GeneratorExit:
        # This fires when client disconnects
        cleanup_client(client_id)
        print(f"Client {client_id} cleaned up")
```

---

### **Pitfall 5 — CORS blocking EventSource**

**Problem:** Frontend on `localhost:3000`, backend on `localhost:5000`. Browser blocks the SSE connection.

**Fix:**
```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app)   # Allow all origins (development)

# Or more specific (production):
CORS(app, origins=["https://yourfrontend.com"])
```

---

### **Pitfall 6 — Redis pub/sub listener not running on all workers**

**Problem:** You use Redis pub/sub for scaling, but only some clients receive broadcasts.

**Why:** The Redis listener thread is started in `__init__` of your manager class, but if gunicorn uses pre-fork workers, the listener might start in the master process only.

**Fix:** Use `@app.before_first_request` or gunicorn's `post_fork` hook:
```python
# gunicorn_config.py
def post_fork(server, worker):
    """This runs in each worker after fork — safe to start threads here"""
    from notifications import manager
    manager.start_redis_listener()
```

---

## **18. Quick reference card**

### **Minimal SSE endpoint**
```python
from flask import Flask, Response
import time

app = Flask(__name__)

@app.route("/events")
def sse():
    def generate():
        while True:
            yield f"data: Hello\n\n"
            time.sleep(1)
    return Response(generate(), mimetype="text/event-stream")
```

### **Event format**
```
id: 123
event: custom-type
data: {"key": "value"}
retry: 5000

```
_(blank line ends the event)_

### **Required headers**
```python
headers = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
```

### **Keepalive comment**
```python
yield ": ping\n\n"   # Lines starting with : are comments
```

### **JS client basics**
```javascript
const es = new EventSource('/events');
es.onopen    = (e) => console.log('connected');
es.onmessage = (e) => console.log(e.data);         // default events
es.onerror   = (e) => console.log('error');
es.addEventListener('custom', (e) => { });          // named events
es.close();
```

### **Auth with token**
```javascript
const es = new EventSource(`/events?token=${yourJWT}`);
```

### **Run command**
```bash
gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:5000 app:app
```

### **stream_with_context when needed**
```python
from flask import stream_with_context
return Response(stream_with_context(generate()), mimetype="text/event-stream")
```