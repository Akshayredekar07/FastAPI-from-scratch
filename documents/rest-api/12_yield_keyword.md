# `yield` Masterclass — From Python Core to FastAPI Production

---

## Table of Contents

1. [What `yield` Actually Is](#1-what-yield-actually-is)
2. [The Analogy That Sticks](#2-the-analogy-that-sticks)
3. [Generator Mechanics — Deep Dry Run](#3-generator-mechanics--deep-dry-run)
4. [Context Managers — The Missing Link](#4-context-managers--the-missing-link)
5. [Why FastAPI Uses `yield` in Dependencies](#5-why-fastapi-uses-yield-in-dependencies)
6. [Scenario 1 — DB Session (SQLModel / SQLAlchemy)](#6-scenario-1--db-session-sqlmodel--sqlalchemy)
7. [Scenario 2 — HTTP Client (httpx)](#7-scenario-2--http-client-httpx)
8. [Scenario 3 — Auth Token Extraction](#8-scenario-3--auth-token-extraction)
9. [Scenario 4 — Nested Dependencies](#9-scenario-4--nested-dependencies)
10. [Scenario 5 — Background Task + Yield](#10-scenario-5--background-task--yield)
11. [Scenario 6 — Pytest Fixture (same pattern)](#11-scenario-6--pytest-fixture-same-pattern)
12. [Common Mistakes](#12-common-mistakes)
13. [Mental Model Summary](#13-mental-model-summary)

---

## 1. What `yield` Actually Is

`return` hands a value to the caller and **ends the function**.  
`yield` hands a value to the caller and **pauses the function** — the local state (variables, position in code) is frozen.  
Calling `next()` on the generator **resumes from the exact line after `yield`**.


Imagine a vending machine that remembers exactly where it left off:

- `return` → like a cashier who hands you all items at once, then closes the register. Memory-heavy, all-or-nothing.
- `yield` → like a machine that drops one item, pauses, waits for your next request, and resumes from the exact same spot. Lightweight, stateful, lazy.

In Python, `yield` turns a normal function into a generator factory. It does not run the function immediately; it returns a generator object. Each time you ask for the next value (`next()` or iteration), the function runs until it hits `yield`, hands you a value, and freezes its entire state (local variables, instruction pointer, call stack).

### How `yield` Works (Mechanics)

| Concept | Description |
| --- | --- |
| Function → Generator | Calling a function with `yield` returns a generator object, not a result |
| Execution Pause | Hits `yield` → returns value → suspends execution |
| State Preservation | Local variables, loop counters, try/except blocks remain alive in memory |
| Resume | Next `next()` or iteration → continues exactly after `yield` |
| Termination | Function exits naturally, hits `return`, or raises `StopIteration` |
| Memory | O(1) auxiliary space (lazy evaluation). No intermediate list built |


```python
# ── CORE DIFFERENCE ──────────────────────────────────────────────────────────

def with_return():
    x = 10
    return x          # function ends here, stack frame destroyed
    print("NEVER")    # unreachable

def with_yield():
    x = 10
    yield x           # function PAUSES here, stack frame kept alive
    print("RESUMED")  # runs when next() is called again

# --- DRY RUN ---

# return version
result = with_return()   # result = 10, function gone
# type(result) → int

# yield version
gen = with_yield()       # nothing executed yet, generator object created
# type(gen) → generator

val = next(gen)          # executes until yield → val = 10
#                          function is PAUSED after yield line

next(gen)                # resumes → prints "RESUMED" → hits end of function
#                          raises StopIteration (no more yields)
```

A function with `yield` **never runs immediately**. It returns a generator object.  
Execution only starts when you call `next()` on it.

---

## 2. The Analogy That Sticks

**Think of `yield` as a pausable video.**

```
Normal function (return):
  ┌──────────────────────┐
  │ Open file            │
  │ Read content         │
  │ Close file ←────────── RETURN fires, function gone
  └──────────────────────┘
  Caller gets content. File is already closed. Can't go back.

Generator (yield):
  ┌──────────────────────┐
  │ Open file            │
  │ Read content         │
  │ PAUSE ←────────────── yield fires, hands content to caller
  │                      │ ← caller is doing work here (request is alive)
  │ Close file ←────────── next()/finally fires after caller is done
  └──────────────────────┘
  File stays open exactly as long as needed. Closes guaranteed.
```

**Real-world map to FastAPI DB session:**

```
Before yield  →  Open DB session          (setup)
yield         →  Give session to endpoint (caller uses it during request)
After yield   →  Close DB session         (teardown — guaranteed even on crash)
```

---

## 3. Generator Mechanics — Deep Dry Run

```python
# ── FULL GENERATOR LIFECYCLE ─────────────────────────────────────────────────

def simple_gen():
    print("A — before yield")
    value = yield 42          # yield sends 42 OUT, can also receive value IN via .send()
    print(f"B — resumed, received: {value}")
    yield 99
    print("C — after second yield")
    # function ends → StopIteration raised automatically

# ─── DRY RUN ─────────────────────────────────────────────────────────────────

gen = simple_gen()
# State: generator created, NO code executed yet
# gen → <generator object simple_gen at 0x...>

step1 = next(gen)
# Execution: print("A — before yield") → hits yield 42
# Output:    "A — before yield"
# step1    = 42
# State:     PAUSED at yield line, local var `value` not yet assigned

step2 = gen.send("hello")
# Execution: yield 42 receives "hello" → value = "hello"
#            print("B — resumed, received: hello") → hits yield 99
# Output:    "B — resumed, received: hello"
# step2    = 99
# State:     PAUSED at second yield

try:
    next(gen)
    # Execution: print("C — after second yield") → function ends
    # Output:    "C — after second yield"
    # Raises:    StopIteration
except StopIteration:
    pass
```

### The `try / finally` Pattern

```python
def resource_gen():
    print("SETUP — acquire resource")
    try:
        yield "the_resource"
        print("NORMAL — code after yield if no exception")
    finally:
        print("TEARDOWN — runs ALWAYS: success, exception, or .close()")

# ─── DRY RUN ─────────────────────────────────────────────────────────────────

gen = resource_gen()

val = next(gen)
# Output: "SETUP — acquire resource"
# val   = "the_resource"

gen.close()
# Throws GeneratorExit into the generator at the yield point
# finally block catches it → Output: "TEARDOWN — runs ALWAYS: ..."
# generator is now dead

# ─── What happens with exception ─────────────────────────────────────────────

gen2 = resource_gen()
next(gen2)
# Output: "SETUP — acquire resource"

try:
    gen2.throw(ValueError("boom"))
    # throws ValueError into gen at yield line
    # finally fires: "TEARDOWN — runs ALWAYS: ..."
    # exception propagates out
except ValueError:
    pass
```

`finally` is the **guarantee** — it fires no matter how the generator dies.  
This is the entire mechanism FastAPI's `yield` dependencies use for cleanup.

---

## 4. Context Managers — The Missing Link

FastAPI converts your `yield` dependency into a context manager internally.  
Understanding `with` unlocks why this works.

```python
# ── CONTEXT MANAGER PROTOCOL ─────────────────────────────────────────────────

class ManagedResource:
    def __enter__(self):
        print("__enter__ → setup")
        return self          # this is what `as` binds to

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("__exit__ → teardown")
        return False         # False = don't suppress exceptions

with ManagedResource() as r:
    print(f"using {r}")
    # Output:
    # __enter__ → setup
    # using <ManagedResource object>
    # __exit__ → teardown

# ── @contextmanager — generator AS context manager ───────────────────────────

from contextlib import contextmanager

@contextmanager
def managed_resource():
    print("__enter__ equivalent — setup")
    resource = "acquired"
    try:
        yield resource        # hands resource to `with` block
    finally:
        print("__exit__ equivalent — teardown")

with managed_resource() as r:
    print(f"using: {r}")

# Output:
# __enter__ equivalent — setup
# using: acquired
# __exit__ equivalent — teardown

# ── FastAPI does this internally ─────────────────────────────────────────────
# Your yield dep function → contextmanager wraps it → context manager runs
# SETUP before yield = __enter__
# TEARDOWN after yield = __exit__
```

---

## 5. Why FastAPI Uses `yield` in Dependencies

```
Request lifecycle with yield dependency:

1. HTTP request arrives at /users/1
2. FastAPI sees Depends(get_session) in endpoint signature
3. FastAPI calls get_session() → gets generator object
4. FastAPI calls next(gen) → runs SETUP code, gets yielded value
5. FastAPI injects yielded value into endpoint as `session` param
6. Endpoint runs (uses session, does DB work)
7. Response is built
8. FastAPI sends response to client
9. FastAPI resumes generator (calls next or close on gen)
10. TEARDOWN code runs (session.close())
11. Request is fully done
```

**Without `yield` (bad pattern):**

```python
# ❌ WRONG — session never guaranteed to close on exception
@app.get("/users/{id}")
def get_user(id: int):
    session = Session(engine)
    user = session.get(User, id)
    # if this raises, session leaks
    return user
```

**With `yield` (correct pattern):**

```python
# ✅ CORRECT — session closes guaranteed
def get_session():
    with Session(engine) as session:
        yield session
        # session.close() fires even if endpoint crashes
```

---

## 6. Scenario 1 — DB Session (SQLModel / SQLAlchemy)

This is your original example. Full explanation + dry run.

```python
from fastapi import FastAPI, Depends
from sqlmodel import SQLModel, Session, create_engine, select, Field
from typing import Annotated

# ── SETUP ─────────────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=True)


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    power: str


SQLModel.metadata.create_all(engine)

app = FastAPI()


# ── THE DEPENDENCY ────────────────────────────────────────────────────────────

def get_session():
    # with Session(engine) as session: is itself a context manager
    # __enter__ → opens DB connection, begins transaction
    # __exit__  → commits or rolls back, closes connection
    with Session(engine) as session:
        yield session
        # execution PAUSES here
        # session is alive, connection is open
        # endpoint runs and uses this session
        # after endpoint is done, `with` block exits → session.close() fires


SessionDep = Annotated[Session, Depends(get_session)]


# ── ENDPOINT ──────────────────────────────────────────────────────────────────

@app.get("/heroes/{hero_id}")
def read_hero(hero_id: int, session: SessionDep):
    hero = session.get(Hero, hero_id)
    return hero


# ─── DRY RUN for GET /heroes/1 ───────────────────────────────────────────────

# Step 1: Request arrives
#         GET /heroes/1

# Step 2: FastAPI resolves Depends(get_session)
#         Calls get_session() → generator object created (no code runs yet)

# Step 3: FastAPI calls next(gen)
#         Executes: enters `with Session(engine) as session:`
#         → Session.__enter__() fires → DB connection opened, session created
#         Hits: yield session
#         → generator PAUSES
#         → FastAPI receives `session` object

# Step 4: FastAPI calls read_hero(hero_id=1, session=<session object>)
#         Executes: session.get(Hero, 1)
#         → SQL: SELECT * FROM hero WHERE id = 1
#         → returns Hero(id=1, name="Akshay", power="AI")

# Step 5: FastAPI builds response JSON and sends to client

# Step 6: FastAPI resumes generator (gen.close() or next())
#         `with` block exits → Session.__exit__() fires
#         → session.close() called
#         → DB connection released back to pool

# Step 7: generator hits end → StopIteration → generator dead
```

---

## 7. Scenario 2 — HTTP Client (httpx)

Same pattern, different resource: external HTTP client.

```python
import httpx
from fastapi import FastAPI, Depends
from typing import Annotated

app = FastAPI()


# ── SYNC CLIENT ───────────────────────────────────────────────────────────────

def get_http_client():
    # Client is created fresh per request
    # connections are pooled inside the client object
    client = httpx.Client(timeout=30.0)
    try:
        yield client          # endpoint uses this client
    finally:
        client.close()        # always closes, even if endpoint raises


HttpClientDep = Annotated[httpx.Client, Depends(get_http_client)]


@app.get("/proxy/github")
def proxy_github(client: HttpClientDep):
    response = client.get("https://api.github.com")
    return {"status": response.status_code}


# ── ASYNC CLIENT ──────────────────────────────────────────────────────────────

async def get_async_client():
    # async with = async context manager
    # __aenter__ and __aexit__ instead of __enter__ / __exit__
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client
        # client stays open while endpoint runs
        # async with exits after yield → client.aclose() fires


AsyncClientDep = Annotated[httpx.AsyncClient, Depends(get_async_client)]


@app.get("/async/proxy/github")
async def async_proxy_github(client: AsyncClientDep):
    response = await client.get("https://api.github.com")
    return {"status": response.status_code}


# ─── DRY RUN for GET /proxy/github ───────────────────────────────────────────

# Step 1: get_http_client() called → generator created (no code yet)

# Step 2: next(gen) called
#         client = httpx.Client(timeout=30.0) → client object created
#         hits yield client → PAUSED
#         FastAPI receives client object

# Step 3: proxy_github(client=<httpx.Client>) runs
#         client.get("https://api.github.com") → real HTTP request made
#         response.status_code → 200

# Step 4: Response sent to user

# Step 5: gen.close() or next() called
#         try block has no more code → falls to finally
#         client.close() → all internal connections closed

# NOTE: Without try/finally, if endpoint raises HTTPException,
#       the finally still runs. Client is ALWAYS closed.
```

---

## 8. Scenario 3 — Auth Token Extraction

`yield` without cleanup — still valid, used for flow control + validation.

```python
from fastapi import FastAPI, Depends, HTTPException, Header
from typing import Annotated

app = FastAPI()

VALID_TOKENS = {"token-akshay-123": {"user_id": 1, "role": "admin"}}


# ── AUTH DEP — yield used just to pass validated data ─────────────────────────

def get_current_user(
    authorization: Annotated[str | None, Header()] = None
):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.removeprefix("Bearer ")

    user = VALID_TOKENS.get(token)
    if user is None:
        raise HTTPException(status_code=403, detail="Invalid token")

    yield user          # no teardown needed, just passing data through
    # nothing after yield = no cleanup
    # this is valid, FastAPI handles it fine


CurrentUserDep = Annotated[dict, Depends(get_current_user)]


@app.get("/profile")
def get_profile(user: CurrentUserDep):
    return {"user_id": user["user_id"], "role": user["role"]}


# ─── DRY RUN for GET /profile with header "Authorization: Bearer token-akshay-123"
#
# Step 1: get_current_user(authorization="Bearer token-akshay-123") called
#         generator created

# Step 2: next(gen) called
#         authorization = "Bearer token-akshay-123" (not None → passes check)
#         token = "token-akshay-123"
#         user = {"user_id": 1, "role": "admin"} (found in VALID_TOKENS)
#         hits yield user → PAUSED
#         FastAPI receives {"user_id": 1, "role": "admin"}

# Step 3: get_profile(user={"user_id": 1, "role": "admin"}) runs
#         returns {"user_id": 1, "role": "admin"}

# Step 4: Response sent, generator resumed, StopIteration, done.

# ─── DRY RUN for invalid token ────────────────────────────────────────────────
#
# Step 2: token = "bad-token"
#         user = VALID_TOKENS.get("bad-token") → None
#         raise HTTPException(403) → generator DIES with exception
#         FastAPI catches it → sends 403 response
#         endpoint never runs
```

---

## 9. Scenario 4 — Nested Dependencies

FastAPI resolves the full dependency tree. Same session instance is shared.

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select
from typing import Annotated

app = FastAPI()


# ── LEVEL 0: Resource ─────────────────────────────────────────────────────────

def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# ── LEVEL 1: Auth using the session ───────────────────────────────────────────

def get_current_user(
    token: str,                  # query param or header
    session: SessionDep          # depends on get_session
):
    user = session.exec(select(Hero).where(Hero.name == token)).first()
    if not user:
        raise HTTPException(status_code=403, detail="Not authenticated")
    yield user                   # passes user down


CurrentUserDep = Annotated[Hero, Depends(get_current_user)]


# ── LEVEL 2: Endpoint using both ──────────────────────────────────────────────

@app.get("/secure/heroes")
def list_heroes(
    session: SessionDep,         # same session instance as get_current_user uses
    current_user: CurrentUserDep
):
    heroes = session.exec(select(Hero)).all()
    return {"requested_by": current_user.name, "heroes": heroes}


# ─── DEPENDENCY RESOLUTION ORDER ─────────────────────────────────────────────
#
# FastAPI builds a DAG (directed acyclic graph):
#
#   list_heroes
#       ├── get_session          ← resolved ONCE, session cached for this request
#       └── get_current_user
#               └── get_session  ← FastAPI returns SAME cached session object
#
# Key insight: If multiple deps declare Depends(get_session),
# FastAPI calls get_session() ONCE per request (use_cache=True by default)
# and reuses the yielded value everywhere.
#
# To force a fresh call: Depends(get_session, use_cache=False)

# ─── DRY RUN for GET /secure/heroes?token=Akshay ─────────────────────────────
#
# Step 1: FastAPI resolves deps in order
#         → calls get_session() → session_gen created
#         → next(session_gen) → session object created (DB connection open)
#         → session cached for this request
#
# Step 2: calls get_current_user(token="Akshay", session=<same session>)
#         → user_gen created
#         → next(user_gen) → DB query: SELECT * FROM hero WHERE name = "Akshay"
#         → user = Hero(id=1, name="Akshay", power="AI")
#         → yield user → PAUSED
#
# Step 3: list_heroes(session=<same session>, current_user=Hero(...)) runs
#         → second SELECT * FROM hero
#         → returns all heroes
#
# Step 4: Response sent
#
# Step 5: Teardown in REVERSE order
#         → user_gen closed (no finally → done)
#         → session_gen closed → with block exits → session.close()
```

---

## 10. Scenario 5 — Background Task + Yield

Cleanup in yield dep fires **before** background tasks.

```python
from fastapi import FastAPI, Depends, BackgroundTasks
from typing import Annotated
import time

app = FastAPI()


def get_request_logger():
    log = {"start": time.time(), "events": []}
    try:
        yield log
    finally:
        # This fires BEFORE background tasks
        duration = time.time() - log["start"]
        print(f"Request done in {duration:.3f}s | Events: {log['events']}")


LogDep = Annotated[dict, Depends(get_request_logger)]


def send_email(address: str):
    # Runs AFTER response is sent AND after yield cleanup
    time.sleep(2)
    print(f"Email sent to {address}")


@app.post("/register")
def register_user(
    email: str,
    log: LogDep,
    background_tasks: BackgroundTasks
):
    log["events"].append("user_validated")
    background_tasks.add_task(send_email, email)
    log["events"].append("email_queued")
    return {"status": "registered"}


# ─── EXECUTION ORDER for POST /register?email=a@b.com ────────────────────────
#
# 1. get_request_logger() setup → log = {"start": ..., "events": []}
# 2. yield log → endpoint gets log
# 3. endpoint runs:
#    - log["events"].append("user_validated")
#    - background_tasks.add_task(send_email, "a@b.com")
#    - log["events"].append("email_queued")
#    - returns {"status": "registered"}
# 4. Response sent to client  ← client sees response HERE
# 5. yield dep cleanup fires:
#    - duration = time.time() - start
#    - print("Request done in 0.001s | Events: ['user_validated', 'email_queued']")
# 6. background task runs:
#    - send_email("a@b.com")
#    - time.sleep(2)
#    - print("Email sent to a@b.com")
#
# Order: endpoint → response sent → dep teardown → background tasks
```

---

## 11. Scenario 6 — Pytest Fixture (Same Pattern)

`yield` in pytest fixtures is **identical mechanics** to FastAPI deps.

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, StaticPool


# ── TEST DB ENGINE ────────────────────────────────────────────────────────────

@pytest.fixture(name="engine")
def engine_fixture():
    # in-memory SQLite, shared connection so tables persist per test
    _engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(_engine)
    yield _engine                          # test gets engine
    SQLModel.metadata.drop_all(_engine)    # teardown after test


@pytest.fixture(name="session")
def session_fixture(engine):              # depends on engine fixture
    with Session(engine) as session:
        yield session                      # test gets session
                                           # with block closes session after test


@pytest.fixture(name="client")
def client_fixture(session):              # depends on session fixture
    def override_get_session():
        yield session                      # inject test session into app

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c                            # test gets TestClient
    app.dependency_overrides.clear()       # cleanup: restore real deps


# ─── DRY RUN for a test using `client` ───────────────────────────────────────
#
# pytest resolves: client → session → engine
#
# 1. engine_fixture()
#    → creates in-memory engine
#    → SQLModel.metadata.create_all → tables created
#    → yield engine → PAUSED
#
# 2. session_fixture(engine=<engine>)
#    → with Session(engine) → session opened
#    → yield session → PAUSED
#
# 3. client_fixture(session=<session>)
#    → overrides get_session with test version
#    → TestClient(app) started
#    → yield client → PAUSED
#
# 4. TEST RUNS here using client
#
# 5. Teardown in REVERSE:
#    → client_fixture resumes: TestClient shuts down, dependency_overrides cleared
#    → session_fixture resumes: with block exits → session.close()
#    → engine_fixture resumes: drop_all → tables destroyed
```

---

## 12. Common Mistakes

```python
# ── MISTAKE 1: Multiple yields in one dep ─────────────────────────────────────

def bad_dep():
    yield "first"
    yield "second"     # ❌ FastAPI only processes the first yield
                       # second yield makes this confusing and is never used
                       # FastAPI uses yield EXACTLY ONCE per dep

# ── MISTAKE 2: return instead of yield when you need cleanup ──────────────────

def bad_session():
    session = Session(engine)
    return session       # ❌ session NEVER closes if endpoint raises
                         # use yield + try/finally

# ── MISTAKE 3: swallowing exceptions in dep ───────────────────────────────────

def bad_dep_swallows():
    try:
        yield
    except Exception:
        pass             # ❌ FastAPI can't detect exceptions now
                         # it won't know to rollback, log, or return 500
                         # if you catch, you MUST re-raise

def correct_dep():
    try:
        yield
    except Exception as e:
        # do something (rollback, log)
        raise            # ✅ always re-raise so FastAPI knows

# ── MISTAKE 4: putting cleanup before yield ───────────────────────────────────

def backwards_dep():
    session = Session(engine)
    session.close()      # ❌ closes BEFORE endpoint runs
    yield session        # endpoint gets a dead session

# ── MISTAKE 5: async/sync mismatch ───────────────────────────────────────────

# If your engine is async (AsyncSession), dep must be async def
# If your engine is sync (Session), dep should be def (not async def)
# Mixing them causes subtle bugs

async def bad_sync_dep():
    with Session(sync_engine) as session:  # ❌ blocking call inside async def
        yield session                       # blocks the event loop

def correct_sync_dep():
    with Session(sync_engine) as session:  # ✅ sync dep, FastAPI handles it
        yield session
```

---

## 13. Mental Model Summary

```
yield in Python
│
├── Makes function a generator (lazy, pausable)
├── Execution pauses AT yield, resumes on next()
├── finally block fires on: normal exit, exception, .close()
│
└── In FastAPI deps specifically:
    │
    ├── Code BEFORE yield  = setup     (runs before endpoint)
    ├── yield <value>      = injection (value given to endpoint)
    ├── Code AFTER yield   = teardown  (runs after response sent)
    │
    ├── FastAPI wraps your gen in a context manager internally
    ├── Multiple deps using same Depends() = cached, one instance per request
    └── Teardown order = REVERSE of setup order (deepest dep tears down first)
```

**One-line rule:**  
> `yield` = "give the caller what they need, and guarantee I clean up when they're done."

---

*Notes by Akshay | FastAPI yield masterclass | 2026*