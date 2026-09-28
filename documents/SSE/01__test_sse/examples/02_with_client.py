
import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

async def event_generator():
    count = 0
    while True:
        count += 1
        # Yield a dict — sse-starlette handles JSON serialization
        yield {
            "data": json.dumps({"count": count, "message": f"Hello number {count}"}),
            "event": "update"
        }
        await asyncio.sleep(2)


@app.get("/events")
async def sse():
    return EventSourceResponse(event_generator())


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>FastAPI SSE Test</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        #status { color: green; font-weight: bold; }
        #messages { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: auto; }
        .msg { margin: 5px 0; padding: 5px; background: #f0f0f0; }
    </style>
</head>
<body>
    <h1>FastAPI SSE Live Updates</h1>
    <p>Status: <span id="status">Connecting...</span></p>
    <div id="messages"></div>
    <button onclick="stopStream()">Stop</button>

    <script>
        const eventSource = new EventSource('/events');
        const messagesDiv = document.getElementById('messages');
        const statusSpan = document.getElementById('status');

        eventSource.onopen = function() {
            statusSpan.textContent = '🟢 Connected';
        };

        // Named event: "update" — matches event: "update" in the yield dict
        eventSource.addEventListener('update', function(event) {
            const data = JSON.parse(event.data);
            const div = document.createElement('div');
            div.className = 'msg';
            div.textContent = `Count: ${data.count} | ${data.message}`;
            messagesDiv.prepend(div);
        });

        eventSource.onerror = function() {
            statusSpan.textContent = '🔴 Reconnecting...';
            statusSpan.style.color = 'red';
        };

        function stopStream() {
            eventSource.close();
            statusSpan.textContent = '⚫ Stopped';
        }
    </script>
</body>
</html>
"""