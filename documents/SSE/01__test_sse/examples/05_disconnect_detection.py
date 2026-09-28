import asyncio
import json
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

EVENT_STORE = [
    {"id": i, "message": f"Stored event {i}", "ts": i * 100}
    for i in range(1, 21)
]


async def event_generator_with_id(request: Request, last_event_id: int | None):

    if last_event_id is not None:
        # client reconnected — send only what it missed
        missed = [e for e in EVENT_STORE if e["id"] > last_event_id]
        print(f"Reconnect: last_id={last_event_id}, missed={len(missed)}")

        for event in missed:
            yield {
                "id": str(event["id"]),
                "event": "missed",
                "data": json.dumps(event)
            }
    else:
        # fresh connection — send last 5 events as history
        print("New client connected")

        for event in EVENT_STORE[-5:]:
            yield {
                "id": str(event["id"]),
                "event": "history",
                "data": json.dumps(event)
            }

    current_id = max(e["id"] for e in EVENT_STORE)

    try:
        while True:
            current_id += 1

            new_event = {
                "id": current_id,
                "message": f"Live event {current_id}",
                "ts": int(time.time())
            }

            EVENT_STORE.append(new_event)

            yield {
                "id": str(new_event["id"]),
                "event": "live",
                "data": json.dumps(new_event)
            }

            await asyncio.sleep(2)

    except asyncio.CancelledError:
        # EventSourceResponse cancels this generator task on client disconnect
        # request.is_disconnected() inside the loop only works between yields
        # CancelledError fires even mid-sleep — so this is the reliable way
        print(f"Generator cancelled at id={current_id}")
        raise


@app.get("/events")
async def events(request: Request):
    # browser auto-reconnect  → sends Last-Event-ID header
    # manual reconnect button → sends ?last_id= query param
    raw = request.headers.get("last-event-id") or request.query_params.get("last_id")
    last_event_id = int(raw) if raw else None

    return EventSourceResponse(
        event_generator_with_id(request, last_event_id)
    )





@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>SSE Demo</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: monospace;
            background: #0f0f0f;
            color: #d4d4d4;
            padding: 24px;
            font-size: 14px;
        }

        h1 {
            font-size: 16px;
            font-weight: normal;
            color: #888;
            margin-bottom: 20px;
            letter-spacing: 0.05em;
        }

        .bar {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
        }

        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #444;
            flex-shrink: 0;
        }

        .dot.connected    { background: #3fb950; }
        .dot.disconnected { background: #f85149; }

        #status-text { color: #888; font-size: 13px; }

        .controls {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }

        button {
            background: #1e1e1e;
            color: #d4d4d4;
            border: 1px solid #333;
            padding: 6px 14px;
            font-family: monospace;
            font-size: 13px;
            cursor: pointer;
            border-radius: 4px;
        }

        button:hover { border-color: #555; background: #252525; }

        .meta {
            font-size: 12px;
            color: #555;
            margin-bottom: 12px;
        }

        #stream {
            border: 1px solid #222;
            border-radius: 4px;
            height: 420px;
            overflow-y: auto;
            padding: 12px;
            display: flex;
            flex-direction: column;
        }

        .entry {
            display: flex;
            gap: 12px;
            padding: 5px 0;
            border-bottom: 1px solid #1a1a1a;
            font-size: 13px;
            line-height: 1.5;
        }

        .entry:last-child { border-bottom: none; }

        .tag {
            font-size: 11px;
            padding: 1px 6px;
            border-radius: 3px;
            flex-shrink: 0;
            align-self: flex-start;
            margin-top: 2px;
            letter-spacing: 0.04em;
        }

        .tag.history { background: #1e2a1e; color: #3fb950; border: 1px solid #2a3d2a; }
        .tag.missed  { background: #2a2516; color: #d29922; border: 1px solid #3d3418; }
        .tag.live    { background: #162030; color: #58a6ff; border: 1px solid #1c3050; }
        .tag.log     { background: #1e1e1e; color: #555;    border: 1px solid #2a2a2a; }

        .id  { color: #555; flex-shrink: 0; }
        .msg { color: #ccc; }
    </style>
</head>
<body>

<h1>SSE / Event Stream</h1>

<div class="bar">
    <div class="dot disconnected" id="dot"></div>
    <span id="status-text">connecting...</span>
</div>

<div class="controls">
    <button onclick="disconnect()">Disconnect</button>
    <button onclick="reconnect()">Reconnect</button>
    <button onclick="clearStream()">Clear</button>
</div>

<div class="meta">
    Last-Event-ID: <span id="last-id">none</span>
</div>

<div id="stream"></div>

<script>
let source = null;
let lastId = null;

function addEntry(type, id, message) {
    if (id) {
        lastId = id;
        document.getElementById("last-id").textContent = id;
    }

    const entry = document.createElement("div");
    entry.className = "entry";
    entry.innerHTML =
        '<span class="tag ' + type + '">' + type + '</span>' +
        (id ? '<span class="id">#' + id + '</span>' : '') +
        '<span class="msg">' + message + '</span>';

    const stream = document.getElementById("stream");

    if (type === "history") {
        stream.appendChild(entry);
    } else {
        stream.prepend(entry);
    }
}

function setConnected(connected, label) {
    document.getElementById("dot").className = "dot " + (connected ? "connected" : "disconnected");
    document.getElementById("status-text").textContent = label;
}

function connect(withLastId) {
    if (source) source.close();

    // on manual reconnect, pass last_id as query param
    // browser auto-reconnect sends Last-Event-ID header automatically
    const url = withLastId && lastId
        ? "/events?last_id=" + lastId
        : "/events";

    addEntry("log", null, "opening connection" + (withLastId && lastId ? " with last_id=" + lastId : "") + "...");

    source = new EventSource(url);

    source.onopen = () => {
        setConnected(true, "connected");
        addEntry("log", null, "connected");
    };

    source.onerror = () => {
        setConnected(false, "reconnecting...");
        addEntry("log", null, "connection lost - browser will retry with Last-Event-ID automatically");
    };

    source.addEventListener("history", e => {
        const d = JSON.parse(e.data);
        addEntry("history", e.lastEventId, d.message);
    });

    source.addEventListener("missed", e => {
        const d = JSON.parse(e.data);
        addEntry("missed", e.lastEventId, d.message);
    });

    source.addEventListener("live", e => {
        const d = JSON.parse(e.data);
        addEntry("live", e.lastEventId, d.message);
    });
}

function disconnect() {
    if (source) {
        source.close();
        source = null;
        setConnected(false, "disconnected");
        addEntry("log", null, "manually disconnected");
    }
}

function reconnect() {
    addEntry("log", null, "manual reconnect triggered");
    connect(true);   // pass lastId as query param so backend sends missed events
}

function clearStream() {
    document.getElementById("stream").innerHTML = "";
    document.getElementById("last-id").textContent = "none";
    lastId = null;
}

connect(false);
</script>

</body>
</html>
"""

