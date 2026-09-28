import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

FAKE_RESPONSES = {
    "weather": "The weather today is looking quite nice. Temperatures will be around 25 degrees with light clouds and a gentle breeze from the southwest.",
    "python": "Python is a high-level programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991.",
    "fastapi": "FastAPI is a modern web framework for building APIs with Python. It is based on standard Python type hints and provides automatic documentation via Swagger UI.",
    "default": "I am an AI assistant and I can help you with many things. Just ask me a question and I will do my best to answer it clearly and concisely."
}


async def stream_ai_response(question: str, request: Request):
    """
    Streams a response token by token — simulates LLM streaming.
    This is exactly how OpenAI/Claude streaming APIs work.
    """
    q = question.lower()
    if "weather" in q:
        response_text = FAKE_RESPONSES["weather"]
    elif "python" in q:
        response_text = FAKE_RESPONSES["python"]
    elif "fastapi" in q:
        response_text = FAKE_RESPONSES["fastapi"]
    else:
        response_text = FAKE_RESPONSES["default"]

    tokens = [word + " " for word in response_text.split()]

    # Send "thinking" status
    yield {
        "event": "thinking",
        "data": json.dumps({"status": "thinking", "question": question})
    }
    await asyncio.sleep(0.3)

    # Stream tokens
    for i, token in enumerate(tokens):
        if await request.is_disconnected():
            break
        yield {
            "event": "token",
            "data": json.dumps({
                "token": token,
                "index": i + 1,
                "total": len(tokens),
                "done": False
            })
        }
        await asyncio.sleep(0.04)  # ~25 tokens per second

    # Done signal
    yield {
        "event": "done",
        "data": json.dumps({
            "total_tokens": len(tokens),
            "done": True
        })
    }


@app.get("/chat/stream")
async def chat_stream(request: Request, question: str = "tell me something"):
    """
    GET /chat/stream?question=what+is+python
    """
    return EventSourceResponse(
        stream_ai_response(question, request),
        headers={"X-Accel-Buffering": "no"}
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<body>
<h1>AI Chat Streaming Demo (FastAPI)</h1>
<input id="question" value="What is FastAPI?" style="width:400px; padding:8px">
<button onclick="ask()">Ask</button>
<div id="answer" style="margin-top:20px; padding:15px; border:1px solid #ccc;
     min-height:100px; font-size:18px; line-height:1.6; white-space:pre-wrap;"></div>
<p id="status" style="color: gray;"></p>

<script>
let currentES = null;

function ask() {
    const question = document.getElementById('question').value;
    const answer = document.getElementById('answer');
    const status = document.getElementById('status');

    if (currentES) currentES.close();
    answer.textContent = '';
    status.textContent = '';

    currentES = new EventSource('/chat/stream?question=' + encodeURIComponent(question));

    currentES.addEventListener('thinking', () => {
        status.textContent = '⏳ AI is thinking...';
    });

    currentES.addEventListener('token', (e) => {
        const data = JSON.parse(e.data);
        answer.textContent += data.token;
        status.textContent = `📝 Streaming... (${data.index}/${data.total})`;
    });

    currentES.addEventListener('done', (e) => {
        const data = JSON.parse(e.data);
        status.textContent = `✅ Done! ${data.total_tokens} tokens`;
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