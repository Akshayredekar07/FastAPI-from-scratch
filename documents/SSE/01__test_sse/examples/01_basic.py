
import asyncio
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()


async def event_generator():
    """
    An async generator that yields events.
    Each yield sends one event to the client.
    """
    count = 0
    while True:
        count += 1
        yield {"data": f"Message count: {count}"}
        await asyncio.sleep(1)



@app.get("/events")
async def sse_endpoint():
    # EventSourceResponse wraps your generator and sets all correct headers
    return EventSourceResponse(event_generator())



@app.get("/")
async def root():
    return {"message": "Go to /events for SSE stream"}


# Run with: uvicorn 1_basic:app --reload