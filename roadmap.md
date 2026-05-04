# FastAPI 2026 Roadmap

A structured, phase-by-phase learning roadmap for mastering FastAPI in 2026 — from Python foundations to production-grade AI agent backends.

---

## Phase 1 — Python & Async Foundations *(Prerequisite)*

> All topics in this phase are **required** before moving forward.

| Topic | What to Learn |
|---|---|
| **Python 3.12 / 3.13** | Type hints, dataclasses, walrus operator, match-case, f-strings, `\|` union types |
| **async / await model** | Event loop, coroutines, `asyncio`, sync-vs-async routes, when NOT to use async |
| **Pydantic v2** | BaseModel, validators, `model_config`, `Field`, serializers, `@computed_field` |
| **ASGI vs WSGI** | Why FastAPI is ASGI, Starlette internals, Uvicorn + Gunicorn workers, lifespan protocol |
| **Environment & tooling** *(tooling)* | `uv` (2026 standard), `pyproject.toml`, `ruff` linting, `mypy` type checks, `pre-commit` |

---

## Phase 2 — Core FastAPI: REST API Fundamentals

| Topic | What to Learn | Tag |
|---|---|---|
| **Path & query params** | Path operations, path params with types, optional query params, enum constraints | REST |
| **Request body** | Pydantic models as body, nested models, multiple body params, `Body(embed=True)` | REST |
| **Response models** | `response_model=`, `response_model_exclude_unset`, status codes, `JSONResponse`, `ORJSONResponse` | REST |
| **APIRouter & versioning** | Modular routers, prefix, tags, `include_router`, `/api/v1/` versioning pattern | REST |
| **Dependency injection** | `Depends()`, nested deps, scoped deps, class-based deps, dep caching per request | REST |
| **Error handling** | HTTPException, custom exception handlers, request validation errors, structured error responses | REST |
| **Form data & file uploads** | `Form()`, `UploadFile`, multipart handling, chunked file writes | REST |
| **OpenAPI & docs** | Auto Swagger UI, ReDoc, custom schema titles, hiding endpoints in prod, OpenAPI 3.1 | REST |

---

## Phase 3 — Database, Auth & Middleware

| Topic | What to Learn | Tag |
|---|---|---|
| **SQLAlchemy 2 async** | `AsyncSession`, `async_scoped_session`, declarative ORM, Alembic migrations | database |
| **MongoDB (Motor)** | Async Motor client, Beanie ODM, document schema via Pydantic | database |
| **Redis async** | `aioredis`, caching layer, pub/sub, rate limit store, session store | database |
| **OAuth2 & JWT** | OAuth2PasswordBearer, JWT encode/decode, access + refresh tokens, token revocation | auth |
| **API keys & RBAC** | API key header auth, role-based access with deps, permission scopes | auth |
| **Middleware** | CORS, GZip, Trusted host, custom middleware class, request-ID injection, timing middleware | middleware |
| **Background tasks** | `BackgroundTasks`, Celery + Redis, ARQ (async task queue), scheduling with APScheduler | async |

---

## Phase 4 — API Types Beyond REST: Realtime, Streaming & gRPC

| Topic | What to Learn | Tag |
|---|---|---|
| **WebSocket (bidirectional)** | Full-duplex, chat apps, live dashboards, `WebSocket` dep injection, connection manager class | realtime |
| **SSE — Server-Sent Events** | `EventSourceResponse`, `StreamingResponse`, unidirectional push, LLM token streaming, resume with `Last-Event-ID` | streaming |
| **StreamingResponse** | Async generators as response body, JSON Lines streaming, file streaming, chunked transfers | streaming |
| **GraphQL** | Strawberry + FastAPI, query/mutation/subscription, DataLoader, mounted ASGI app | API type |
| **gRPC (via grpcio)** | protobuf definitions, gRPC server alongside FastAPI, when to use gRPC vs REST | API type |
| **MCP (Model Context Protocol)** | FastMCP + SSE transport, mounting MCP at `/mcp`, exposing tools to AI agents, embedded vs bridge pattern | AI-native |
| **Webhook endpoints** | Inbound webhooks, payload signature verification, idempotency keys, retry handling | event-driven |

---

## Phase 5 — ML Inference & AI Agents

| Topic | What to Learn | Tag |
|---|---|---|
| **Model serving patterns** | Load model at startup with `lifespan`, app state, singleton pattern, model warm-up | ML |
| **Sync inference (CPU-bound)** | Run blocking inference in `asyncio.run_in_executor`, `ProcessPoolExecutor` for GIL bypass | ML |
| **Batching & queuing** | Request batching with asyncio Queue, dynamic batching, latency vs throughput trade-off | ML |
| **LLM streaming via SSE** | Stream LLM tokens from OpenAI / HuggingFace / LangChain via async generator → SSE response | LLM |
| **RAG pipeline backend** | FastAPI as RAG service: embed → Qdrant/Milvus/FAISS query → LLM → stream response | RAG |
| **LangGraph / LangChain agent backend** | Expose agent graph via FastAPI, async invoke, streaming agent steps over SSE, tool call results | agent |
| **MCP server for agents** | Expose FastAPI endpoints as MCP tools, `@mcp.tool()` decorator, agent discovers and calls your API | MCP |
| **Multimodal inference** | Image upload → base64 → vision model, audio upload → Wav2Vec2, binary response with correct content-type | multimodal |

---

## Phase 6 — Production, Testing & Deployment

| Topic | What to Learn | Tag |
|---|---|---|
| **Testing** | `pytest` + `httpx.AsyncClient`, `TestClient`, fixtures, mocking deps, `pytest-asyncio` | testing |
| **Observability** | Structured logging (loguru), OpenTelemetry traces, Prometheus metrics, Sentry integration | prod |
| **Security hardening** | Rate limiting, input sanitisation, secrets via env, HTTPS enforced, OWASP top-10 mitigations | prod |
| **Docker + Docker Compose** | Multi-stage Dockerfile (python:3.12-slim), compose for local DB + Redis + app stack | deploy |
| **Gunicorn + Uvicorn workers** | UvicornWorker class, worker count formula, graceful shutdown, lifespan events in prod | deploy |
| **Kubernetes / cloud deploy** | K8s Deployment + Service, health probes, HPA, Render / Railway for quick deploys | deploy |
| **CI/CD pipeline** | GitHub Actions: lint → test → docker build → deploy; environment secrets management | deploy |

---

## API Types Comparison

| API Type | Protocol | Direction | Best For |
|---|---|---|---|
| **REST** | HTTP/1.1, HTTP/2 | Request-Response | CRUD, resource-based APIs |
| **WebSocket** | WS (TCP upgrade) | Full-duplex | Chat, live collab, gaming |
| **SSE** | HTTP (text/event-stream) | Server → Client only | LLM streaming, live feeds, MCP transport |
| **GraphQL** | HTTP/WS | Query / Subscription | Flexible client queries, nested data |
| **gRPC** | HTTP/2 + protobuf | Bidirectional streams | Microservice-to-microservice, low latency |
| **MCP (SSE transport)** | HTTP SSE / Streamable HTTP | Server → Agent | AI agent tool discovery and calling |
| **Webhooks** | HTTP POST | Push to client URL | Event-driven integrations, payment callbacks |

---

## Project Folder Structures

### Small / Microservice

```
my-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app factory, lifespan
│   ├── dependencies.py  # shared Depends()
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── users.py
│   │   └── items.py
│   ├── schemas/         # Pydantic models (request/response)
│   │   └── user.py
│   ├── models/          # ORM / DB models
│   │   └── user.py
│   ├── services/        # business logic
│   │   └── user_service.py
│   ├── core/
│   │   ├── config.py    # pydantic-settings BaseSettings
│   │   └── security.py
│   └── db/
│       ├── database.py  # async engine, session factory
│       └── alembic/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

### Full-Stack App

```
fullstack-app/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── users.py
│   │   │   │   └── items.py
│   │   │   └── deps.py      # shared dependencies
│   │   ├── ws/              # WebSocket routers
│   │   │   └── chat.py
│   │   ├── sse/             # SSE streaming endpoints
│   │   │   └── notifications.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── db/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/              # React / Next.js
│   ├── src/
│   └── package.json
├── docker-compose.yml     # backend + frontend + db + redis
└── .env.example
```

### ML Inference Service

```
ml-inference-service/
├── app/
│   ├── main.py              # lifespan: load model on startup
│   ├── api/
│   │   ├── predict.py       # POST /predict, POST /predict/stream
│   │   └── health.py        # GET /health, GET /ready
│   ├── core/
│   │   ├── config.py        # model path, batch size, device
│   │   └── logging.py
│   ├── models/              # ML model wrappers
│   │   ├── __init__.py
│   │   ├── base.py          # abstract BaseModel class
│   │   └── classifier.py    # EfficientNet, ViT, etc.
│   ├── services/
│   │   ├── inference.py     # preprocess → infer → postprocess
│   │   └── batch_queue.py   # asyncio Queue for dynamic batching
│   └── schemas/
│       └── predict.py       # PredictRequest, PredictResponse
├── weights/                 # model checkpoints (gitignored)
├── tests/
├── Dockerfile               # CUDA base if GPU needed
└── pyproject.toml
```

### AI Agent Backend

```
ai-agent-backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── agent.py         # POST /run, GET /stream (SSE)
│   │   ├── rag.py           # POST /ingest, POST /query
│   │   └── chat.py          # WebSocket /ws/chat
│   ├── mcp/                 # MCP server definition
│   │   ├── server.py        # FastMCP("agent-mcp")
│   │   └── tools.py         # @mcp.tool() definitions
│   ├── agents/
│   │   ├── graph.py         # LangGraph StateGraph definition
│   │   ├── state.py         # TypedDict agent state
│   │   └── nodes.py         # graph node functions
│   ├── rag/
│   │   ├── embedder.py
│   │   ├── vector_store.py  # Qdrant / Milvus / FAISS
│   │   └── retriever.py
│   ├── core/
│   │   ├── config.py
│   │   └── llm.py           # LLM client singleton
│   └── schemas/
├── tests/
├── Dockerfile
└── pyproject.toml
```

### Domain-Driven Monolith *(Netflix Dispatch-inspired)*

```
domain-driven-monolith/
├── alembic/
├── src/
│   ├── main.py              # app factory, router registration
│   ├── config.py            # global Pydantic BaseSettings
│   ├── database.py          # async engine, session dep
│   ├── auth/                # domain: auth
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── service.py
│   │   ├── dependencies.py
│   │   └── exceptions.py
│   ├── users/               # domain: users
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── service.py
│   │   └── repository.py    # data access layer
│   ├── orders/              # domain: orders
│   │   └── ...              # same pattern
│   └── shared/              # cross-domain utils
│       ├── pagination.py
│       └── exceptions.py
├── tests/
│   ├── auth/
│   ├── users/
│   └── conftest.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── pyproject.toml
```