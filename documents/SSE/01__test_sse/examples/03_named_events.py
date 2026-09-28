import asyncio
import json
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()


async def mixed_event_generator():
    """Sends different event types at different times"""
    count = 0
    while True:
        count += 1

        if count % 5 == 0:
             # Notification event every 5 counts
             yield {
                 'event': "notification",
                 "data" : json.dumps({"text": f"Alert! Event #{count}", "level": "warning"})
             }

        elif count % 3 == 0:
            # Price update every 3 counts
            yield {
                "event": "price-update",
                "data": json.dumps({
                    "symbol": "BTC",
                    "price": round(40000 + random.uniform(-500, 500), 2)
                })
            }

        else:
            # Default message (no event field = onmessage fires)
            yield {
                "data": json.dumps({"count": count, "type": "default"})
            }

        await asyncio.sleep(0.1)



@app.get("/events")
async def sse():
    return EventSourceResponse(mixed_event_generator())


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>Named Events Demo</h1>
<div id="log" style="font-family:monospace; white-space:pre; border:1px solid #ccc;
     padding:10px; height:300px; overflow:auto;"></div>

<script>
    const es = new EventSource('/events');
    const log = document.getElementById('log');

    function addLog(type, data) {
        log.textContent = `[${type}] ${JSON.stringify(data)}\n` + log.textContent;
    }

    // Catches events WITHOUT event: field
    es.onmessage = (e) => addLog('message', JSON.parse(e.data));

    // Named event listeners
    es.addEventListener('notification', (e) => addLog('🔔 NOTIFICATION', JSON.parse(e.data)));
    es.addEventListener('price-update', (e) => addLog('💰 PRICE', JSON.parse(e.data)));
</script>
</body>
</html>
"""
