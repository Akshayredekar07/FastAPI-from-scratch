# **FastAPI Notes**

Source notes: Django "FirstProject / testapp" walkthrough.
Goal: same flow (project, application, register, view, url, runserver, request/response), rebuilt in FastAPI so you can read, type, and experiment.

FastAPI project = one ASGI application object + multiple routers (the "applications") + configuration.

---

### **0. Django to FastAPI Mapping (read this first)**

| Django concept | FastAPI equivalent | Note |
|---|---|---|
| `django-admin startproject FirstProject` | Create folder + `main.py` manually | No generator. You own the structure. |
| `manage.py` | `main.py` (creates `app`) + `fastapi` CLI / `uvicorn` | `manage.py runserver` becomes `fastapi dev main.py` |
| `settings.py` | `core/config.py` using `pydantic-settings` + `.env` | Settings are a typed class, not a module of constants |
| `INSTALLED_APPS` | `app.include_router(...)` in `main.py` | Registering = including the router |
| `python manage.py startapp testapp` | Create folder `testapp/` with `router.py` | An "app" = a package holding an `APIRouter` |
| `views.py` | Path operation functions (in `router.py`) | Function decorated with `@router.get(...)` |
| `urls.py` (`urlpatterns`) | The decorator itself: `@router.get("/hello")` | URL and view are declared together |
| `HttpRequest` input | Typed function parameters (or `Request`) | FastAPI parses and validates for you |
| `HttpResponse` output | Return dict / Pydantic model / `Response` subclass | Dict is auto-converted to JSON |
| FBV (Function Based Views) | Path operation functions | The default and the main way |
| CBV (Class Based Views) | Class-based dependencies, or class-based routers (third-party) | Not native like Django CBVs |
| `models.py` (ORM) | SQLAlchemy / SQLModel models | Not built in |
| `migrations/` | Alembic | Not built in |
| `admin.py` (admin site) | None built in (SQLAdmin, etc. are add-ons) | Big difference |
| `tests.py` | `tests/` with `pytest` + `TestClient` | |
| `wsgi.py` / `asgi.py` | Only ASGI. `app` object in `main.py` is the ASGI app | FastAPI has no WSGI mode |
| Django built-in dev server | `uvicorn` (launched by `fastapi dev`) | Default port 8000 |
| Browsable pages only | Auto docs at `/docs` and `/redoc` | Free interactive API testing |

Key mindset shift: Django is "batteries included" (ORM, admin, auth, templates, forms). FastAPI is a thin, fast layer for building APIs with validation and docs; you pick the rest.

---

### **1. Environment Setup**

Work inside a virtual environment (keeps packages per project).

```bash
mkdir FirstProject
cd FirstProject

python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install "fastapi[standard]"
```

`fastapi[standard]` installs: `fastapi`, `uvicorn` (server), `pydantic`, `python-multipart`, `jinja2`, `httpx` and the `fastapi` CLI.

Optional extras used later:

```bash
pip install pydantic-settings pytest
```

Freeze dependencies:

```bash
pip freeze > requirements.txt
```

Check installation:

```bash
python -c "import fastapi; print(fastapi.__version__)"
```

---

### **2. Creating the Project** (equivalent of `django-admin startproject`)

There is no command. The smallest possible project is one file.

File: `FirstProject/main.py`

```python
from fastapi import FastAPI

app = FastAPI(title="FirstProject")


@app.get("/")
def root():
    return {"message": "FastAPI is running"}
```

Minimal layout:

```
FirstProject
    |- .venv/
    |- main.py          (entry point: creates app; replaces manage.py + root urls.py)
    |- requirements.txt
```

---

### **3. Running the Server** (equivalent of `python manage.py runserver`)

Development mode with auto reload:

```bash
fastapi dev main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload
```

Meaning of `main:app`: file `main.py`, object named `app`.

Default port is 8000:

```
http://127.0.0.1:8000/          -> {"message": "FastAPI is running"}
http://127.0.0.1:8000/docs      -> Swagger UI (interactive)
http://127.0.0.1:8000/redoc     -> ReDoc
http://127.0.0.1:8000/openapi.json -> raw OpenAPI schema
```

Useful options:

```bash
uvicorn main:app --reload --port 9000
uvicorn main:app --reload --host 0.0.0.0
```

Production style (no reload, multiple workers):

```bash
fastapi run main.py
uvicorn main:app --workers 4
```

---

### **4. Project Structure With an Application** (equivalent of `startapp testapp`)

In Django: project = multiple applications + configuration.
In FastAPI: project = one `FastAPI()` object + multiple `APIRouter`s + configuration.

Create these folders and files manually:

```
FirstProject
    |- .venv/
    |- .env
    |- requirements.txt
    |- main.py                    (project entry, registers routers)
    |- core
    |   |- __init__.py
    |   |- config.py              (settings.py equivalent)
    |- testapp                    (application name: testapp)
    |   |- __init__.py            (makes folder a python package)
    |   |- router.py              (views.py + urls.py combined)
    |   |- schemas.py             (request/response data shapes, Pydantic)
    |   |- models.py              (database models, optional for now)
    |   |- dependencies.py        (reusable dependencies, optional)
    |   |- services.py            (business logic, optional)
    |- tests
        |- __init__.py
        |- test_testapp.py        (tests.py equivalent)
```

Terminal commands to create it (Linux/macOS):

```bash
mkdir core testapp tests
touch core/__init__.py testapp/__init__.py tests/__init__.py
touch core/config.py testapp/router.py testapp/schemas.py testapp/models.py
touch testapp/dependencies.py testapp/services.py tests/test_testapp.py
touch .env
```

Windows PowerShell:

```powershell
mkdir core, testapp, tests
ni core\__init__.py, testapp\__init__.py, tests\__init__.py
ni core\config.py, testapp\router.py, testapp\schemas.py, testapp\models.py
ni testapp\dependencies.py, testapp\services.py, tests\test_testapp.py, .env
```

What each file in `testapp` is for (mirror of the Django notes):

```
testapp
    |- __init__.py      --> consider the container folder as python package
    |- router.py        --> view functions AND their url patterns (Django: views.py + urls.py)
    |- schemas.py       --> shapes of incoming/outgoing data (Django: forms/serializers)
    |- models.py        --> database model classes (Django: models.py)
    |- dependencies.py  --> reusable pieces injected into views (auth, db session)
    |- services.py      --> business logic kept out of views
tests
    |- test_testapp.py  --> test cases (Django: tests.py)
```

Not present in FastAPI: `admin.py`, `apps.py`, `migrations/` (Alembic adds an `alembic/` folder later).

Important things (Django to FastAPI):

```
Django                                   FastAPI
django-admin startproject FirstProject   main.py
    settings.py                              core/config.py
    urls.py                                  main.py (include_router) + decorators
    manage.py                                fastapi dev main.py
python manage.py startapp testapp        testapp/ package
    views.py                                 testapp/router.py
```

---

### **5. Activities Required For the Application**

Django checklist:

```
created a project
created an application
add that application inside settings.py
define view function inside views.py
define urlpatterns for view inside urls.py file
runserver
send request
```

FastAPI checklist:

```
created a project folder + main.py
created an application package (testapp)
define a router and view function inside testapp/router.py
register the router inside main.py (replaces INSTALLED_APPS + urls.py include)
runserver (fastapi dev main.py)
send request
```

#### **5.1 Configuration (settings.py equivalent)**

File: `.env`

```
APP_NAME=FirstProject
DEBUG=true
```

File: `core/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FirstProject"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
```

Values come from environment variables or `.env`, are type-converted (`"true"` becomes `True`) and validated at startup. Django has one giant `settings.py`; here it is a typed class.

#### **5.2 Create views (path operation functions)**

Django:
- views.py is part of the application, not the project
- input for view -> `HttpRequest`
- output for view -> `HttpResponse`
- two ways: FBVs and CBVs

FastAPI:
- the view is called a **path operation function**
- it lives in the application's `router.py`
- input: the parameters you declare (path, query, body, headers), or the raw `Request`
- output: whatever you return (dict, list, Pydantic model) or a `Response` object
- each view can be `def` (sync, runs in a thread pool) or `async def` (runs in the event loop)

##### **a. Function Based Views (FBVs)** (the standard way)

File: `testapp/router.py`

```python
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/testapp", tags=["testapp"])


# Django: def display(request): return HttpResponse(s)
@router.get("/hello", response_class=HTMLResponse)
def display():
    s = "<h1>Welcome to FastAPI classes purely nursery level classes</h1>"
    return HTMLResponse(content=s)
```

Rules (compare to Django notes):
- Django: each view takes at least one argument `request`. FastAPI: arguments are optional; declare only what you need. Add `request: Request` only if you need the raw request.
- Django: each view must return an `HttpResponse`. FastAPI: return any JSON-serializable data and it is converted for you; return a `Response` subclass when you need full control.

Return types at a glance:

```python
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse

router = APIRouter()


@router.get("/json")
def as_json():
    return {"msg": "dict becomes JSON automatically"}      # default


@router.get("/html", response_class=HTMLResponse)
def as_html():
    return "<h1>HTML page</h1>"


@router.get("/text", response_class=PlainTextResponse)
def as_text():
    return "plain text"


@router.get("/custom")
def custom():
    return JSONResponse(content={"a": 1}, status_code=201, headers={"X-Demo": "yes"})


@router.get("/go")
def go():
    return RedirectResponse(url="/testapp/hello")
```

Accessing the raw request (the Django `request` object equivalent):

```python
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/whoami")
def whoami(request: Request):
    return {
        "method": request.method,
        "url": str(request.url),
        "client": request.client.host,
        "user_agent": request.headers.get("user-agent"),
    }
```

##### **b. Class Based Views (CBVs)**

FastAPI has no built-in CBV like Django's `View` / `TemplateView`. Three practical options:

1. Class as a dependency (native, most useful):

```python
from fastapi import APIRouter, Depends

router = APIRouter()


class Pagination:
    def __init__(self, page: int = 1, size: int = 10):
        self.page = page
        self.size = size


@router.get("/items")
def list_items(p: Pagination = Depends()):
    return {"page": p.page, "size": p.size}
```

2. Callable class instance registered as a route:

```python
class Greeter:
    def __init__(self, greeting: str):
        self.greeting = greeting

    def __call__(self, name: str = "world"):
        return {"msg": f"{self.greeting}, {name}"}


router.add_api_route("/greet", Greeter("Hello"), methods=["GET"])
```

3. Third-party class-based routing (`fastapi-utils` `@cbv`) or organize logic in service classes called from function views. Most FastAPI codebases just use function views plus service classes.

#### **5.3 Define the URL pattern**

Django: URL patterns go in the project-level `urls.py`, using `path()` (older versions used `url()`).

FastAPI: the URL is declared in the decorator. The only "project level" step is registering the router.

File: `main.py`

```python
from fastapi import FastAPI

from core.config import settings
from testapp.router import router as testapp_router

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Django: INSTALLED_APPS += ["testapp"]  and  path("testapp/", include("testapp.urls"))
app.include_router(testapp_router)


@app.get("/")
def root():
    return {"message": "FastAPI is running"}
```

Compare with the Django example:

```python
# Django urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("hello/", views.display),
]
```

```python
# FastAPI equivalent (final URL is /testapp/hello because router prefix="/testapp")
@router.get("/hello")
def display(): ...
```

Optional: keep Django-style separation of views and URL table (experiment).

File: `testapp/views.py`

```python
def display():
    return {"msg": "hello from views.py"}


def show_item(item_id: int):
    return {"item_id": item_id}
```

File: `testapp/urls.py`

```python
from fastapi import APIRouter

from testapp import views

router = APIRouter(prefix="/testapp")

router.add_api_route("/hello", views.display, methods=["GET"])
router.add_api_route("/items/{item_id}", views.show_item, methods=["GET"])
```

Then in `main.py`: `from testapp.urls import router` and `app.include_router(router)`. Both styles work; the decorator style is the norm.

---

### **6. Request / Response Flow**

Django flow from the notes:

```
http://127.0.0.1:8000/hello
    |-> web server will get request
    |-> open urls.py and identify the corresponding view function
    |-> execute the view function and return HttpResponse to the end user
```

FastAPI flow:

```
Client (browser / curl / Postman)
    |
    |  GET http://127.0.0.1:8000/testapp/hello
    v
Uvicorn (ASGI server) receives the HTTP request
    |
    v
FastAPI app object (main.py)
    |
    v
Middleware stack (CORS, logging, ... in order)
    |
    v
Router matching: finds the route whose path + method match
    (routes come from decorators + include_router)
    |
    v
Dependency resolution (Depends: db session, auth, pagination)
    |
    v
Request parsing + validation by Pydantic
    (path params, query params, headers, body)
    |-- invalid --> automatic 422 error response
    v
Your view function runs  (def -> thread pool, async def -> event loop)
    |
    v
Return value -> response_model filtering -> serialization
    |
    v
Response goes back through middleware
    |
    v
Uvicorn sends HTTP response to client
```

Steps to test end to end:

```bash
fastapi dev main.py
curl http://127.0.0.1:8000/testapp/hello
```

---

### **7. Web Servers**

Django notes: Django provides an inbuilt web server; others are Tomcat, WebLogic, WebSphere, JBoss, Resin, Jetty (those are Java servers, listed for comparison).

FastAPI:

```
webservers (ASGI):
    |- uvicorn        (the standard; used by fastapi dev / fastapi run)
    |- hypercorn      (HTTP/2, HTTP/3 support)
    |- daphne         (from the Django Channels team)
    |- granian        (Rust based)
    |- gunicorn + uvicorn workers  (common production process manager)
```

WSGI vs ASGI:

```
Django  : wsgi.py (sync, classic)  and asgi.py (async support)
FastAPI : ASGI only. The `app` object is the ASGI application.
```

FastAPI has no "inbuilt" server in the Django sense; `fastapi dev` is a thin wrapper that starts uvicorn for you.

Production example with gunicorn:

```bash
pip install gunicorn
gunicorn main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

---

### **8. Beyond the Notes: Things Django Gave You That You Now Add Yourself**

#### **8.1 URL parameters (path + query)**

Django: `path("items/<int:pk>/", views.item)`.

```python
@router.get("/items/{item_id}")
def get_item(item_id: int, q: str | None = None, limit: int = 10):
    return {"item_id": item_id, "q": q, "limit": limit}
```

- `item_id` is in the path so it is a path parameter; `int` gives automatic validation.
- `q` and `limit` are not in the path so they are query params: `/testapp/items/5?q=abc&limit=20`.
- `/testapp/items/abc` returns 422 with a clear error.

#### **8.2 Request body with Pydantic (Django forms/serializers equivalent)**

File: `testapp/schemas.py`

```python
from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    price: float = Field(gt=0)
    in_stock: bool = True


class ItemOut(BaseModel):
    id: int
    name: str
    price: float
    in_stock: bool
```

File: `testapp/router.py` (add)

```python
from fastapi import APIRouter, HTTPException, status

from testapp.schemas import ItemCreate, ItemOut

router = APIRouter(prefix="/testapp", tags=["testapp"])

fake_db: dict[int, dict] = {}


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate):
    new_id = len(fake_db) + 1
    record = {"id": new_id, **payload.model_dump()}
    fake_db[new_id] = record
    return record


@router.get("/items/{item_id}", response_model=ItemOut)
def read_item(item_id: int):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return fake_db[item_id]


@router.get("/items", response_model=list[ItemOut])
def list_items():
    return list(fake_db.values())
```

Try it:

```bash
curl -X POST http://127.0.0.1:8000/testapp/items \
  -H "Content-Type: application/json" \
  -d '{"name":"pen","price":10.5}'

curl http://127.0.0.1:8000/testapp/items
curl http://127.0.0.1:8000/testapp/items/1
```

`response_model` filters the output to `ItemOut` fields (useful to hide passwords, internal fields).

#### **8.3 All HTTP methods**

```python
@router.put("/items/{item_id}", response_model=ItemOut)
def replace_item(item_id: int, payload: ItemCreate):
    if item_id not in fake_db:
        raise HTTPException(404, "Item not found")
    fake_db[item_id] = {"id": item_id, **payload.model_dump()}
    return fake_db[item_id]


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    if fake_db.pop(item_id, None) is None:
        raise HTTPException(404, "Item not found")
```

#### **8.4 Dependency injection (Django middleware/decorators/mixins equivalent)**

File: `testapp/dependencies.py`

```python
from fastapi import Header, HTTPException


def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != "secret123":
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
```

Use per route or for the whole router:

```python
from fastapi import Depends
from testapp.dependencies import require_api_key


@router.get("/secure")
def secure(key: str = Depends(require_api_key)):
    return {"ok": True}


# whole router protected:
# router = APIRouter(prefix="/testapp", dependencies=[Depends(require_api_key)])
```

#### **8.5 Database (Django ORM + migrations equivalent)**

Django gives `models.py` + `migrate` + `db.sqlite3`. In FastAPI use SQLModel (simple) or SQLAlchemy, plus Alembic for migrations.

```bash
pip install sqlmodel
```

File: `testapp/models.py`

```python
from sqlmodel import SQLModel, Field


class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float
```

File: `core/db.py`

```python
from sqlmodel import SQLModel, Session, create_engine

engine = create_engine("sqlite:///db.sqlite3", connect_args={"check_same_thread": False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
```

File: `main.py` (lifespan creates tables at startup)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.db import create_db_and_tables
from testapp.router import router as testapp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(testapp_router)
```

Use in a view:

```python
from fastapi import Depends
from sqlmodel import Session, select

from core.db import get_session
from testapp.models import Item


@router.post("/db-items", response_model=Item)
def create_db_item(item: Item, session: Session = Depends(get_session)):
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/db-items", response_model=list[Item])
def list_db_items(session: Session = Depends(get_session)):
    return session.exec(select(Item)).all()
```

`create_all` is fine for learning. For real schema changes use Alembic (`pip install alembic`, `alembic init alembic`, `alembic revision --autogenerate`, `alembic upgrade head`), the equivalent of `makemigrations` + `migrate`.

#### **8.6 Templates (Django templates equivalent)**

FastAPI is API first, but supports Jinja2 HTML.

```
FirstProject
    |- templates
        |- hello.html
```

File: `templates/hello.html`

```html
<h1>Hello {{ name }}</h1>
```

```python
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


@router.get("/page")
def page(request: Request, name: str = "Akshay"):
    return templates.TemplateResponse(request=request, name="hello.html", context={"name": name})
```

Static files (Django `staticfiles`):

```python
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
```

#### **8.7 Middleware and CORS**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Custom middleware:

```python
import time
from fastapi import Request


@app.middleware("http")
async def add_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.4f}"
    return response
```

#### **8.8 Async vs sync views**

```python
import asyncio


@router.get("/sync")
def sync_view():
    return {"kind": "sync (thread pool)"}


@router.get("/async")
async def async_view():
    await asyncio.sleep(1)        # non-blocking wait
    return {"kind": "async (event loop)"}
```

Rule: inside `async def` never call blocking code (`time.sleep`, `requests.get`, blocking DB drivers) because it freezes the whole server. Use `def` for blocking code or use async libraries (`httpx.AsyncClient`, async DB drivers).

#### **8.9 Background tasks**

```python
from fastapi import BackgroundTasks


def write_log(msg: str):
    with open("log.txt", "a") as f:
        f.write(msg + "\n")


@router.post("/notify")
def notify(email: str, background: BackgroundTasks):
    background.add_task(write_log, f"notified {email}")
    return {"status": "queued"}
```

#### **8.10 Testing (tests.py equivalent)**

File: `tests/test_testapp.py`

```python
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "FastAPI is running"}


def test_hello():
    r = client.get("/testapp/hello")
    assert r.status_code == 200
    assert "Welcome" in r.text


def test_create_and_read_item():
    r = client.post("/testapp/items", json={"name": "pen", "price": 10})
    assert r.status_code == 201
    item_id = r.json()["id"]
    assert client.get(f"/testapp/items/{item_id}").json()["name"] == "pen"


def test_validation_error():
    r = client.post("/testapp/items", json={"name": "x", "price": -1})
    assert r.status_code == 422
```

Run from the project root:

```bash
pytest -v
```

#### **8.11 Error handling**

```python
from fastapi import Request
from fastapi.responses import JSONResponse


class BusinessError(Exception):
    def __init__(self, message: str):
        self.message = message


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    return JSONResponse(status_code=400, content={"error": exc.message})
```

---

### **9. Complete Working Example (copy, run, experiment)**

Layout:

```
FirstProject
    |- main.py
    |- core/__init__.py
    |- core/config.py
    |- testapp/__init__.py
    |- testapp/schemas.py
    |- testapp/router.py
```

`main.py`

```python
from fastapi import FastAPI

from core.config import settings
from testapp.router import router as testapp_router

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(testapp_router)


@app.get("/")
def root():
    return {"message": "FastAPI is running"}
```

`core/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FirstProject"
    debug: bool = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
```

`testapp/schemas.py`

```python
from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    price: float = Field(gt=0)


class ItemOut(ItemCreate):
    id: int
```

`testapp/router.py`

```python
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from testapp.schemas import ItemCreate, ItemOut

router = APIRouter(prefix="/testapp", tags=["testapp"])

fake_db: dict[int, dict] = {}


@router.get("/hello", response_class=HTMLResponse)
def display():
    return "<h1>Welcome to FastAPI classes purely nursery level classes</h1>"


@router.get("/whoami")
def whoami(request: Request):
    return {"method": request.method, "url": str(request.url)}


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate):
    new_id = len(fake_db) + 1
    fake_db[new_id] = {"id": new_id, **payload.model_dump()}
    return fake_db[new_id]


@router.get("/items", response_model=list[ItemOut])
def list_items():
    return list(fake_db.values())


@router.get("/items/{item_id}", response_model=ItemOut)
def read_item(item_id: int):
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return fake_db[item_id]
```

Run and test:

```bash
fastapi dev main.py
# open http://127.0.0.1:8000/docs and use "Try it out" on each endpoint
```

Dry run of `POST /testapp/items` with `{"name": "pen", "price": 10}`:

```
1. Uvicorn receives POST /testapp/items
2. Router matches create_item (prefix /testapp + path /items)
3. Pydantic validates body against ItemCreate (name 2-50 chars, price > 0)
4. create_item runs: new_id = 0 + 1 = 1, stores {"id":1,"name":"pen","price":10.0}
5. response_model=ItemOut filters output; status 201
6. Client receives {"id":1,"name":"pen","price":10.0}
```

---

### **10. Common Errors and Fixes**

```
Error: Error loading ASGI app. Could not import module "main"
Fix  : run the command from the folder that contains main.py; check the file name.

Error: ModuleNotFoundError: No module named 'testapp'
Fix  : run from project root; make sure testapp/__init__.py exists.

Error: 404 Not Found on /hello
Fix  : router has prefix="/testapp", so the URL is /testapp/hello. Also confirm app.include_router(...) is called.

Error: 422 Unprocessable Entity
Fix  : request data failed validation. Read the "detail" list in the response; it names the field and reason.

Error: 405 Method Not Allowed
Fix  : you sent GET to a POST route (or reverse).

Error: server freezes under load
Fix  : blocking call inside async def. Use def, or an async library.

Error: changes not appearing
Fix  : start with --reload (fastapi dev does this by default).

Error: ImportError: circular import
Fix  : do not import main.py from inside routers; put shared objects in core/.
```

---

### **11. Practice Roadmap (do in order)**

```
Step 1  Reproduce sections 2 and 3: root endpoint, open /docs
Step 2  Add testapp with /hello returning HTML (section 5.2)
Step 3  Add /whoami and print request.headers
Step 4  Add path + query params: /items/{id}?q=
Step 5  Add POST with Pydantic body and validation rules
Step 6  Add PUT, DELETE, 404 handling
Step 7  Add a dependency (API key) and protect one route
Step 8  Replace fake_db with SQLModel + sqlite (section 8.5)
Step 9  Write pytest tests for every endpoint
Step 10 Add a second app "blogapp" as another router; include both in main.py
```

Challenge questions:

1. Change the router prefix and predict the new URL before testing.
2. Send `price: "abc"` and read the 422 body. Which field path does it report?
3. Make `/hello` `async def` and add `await asyncio.sleep(2)`. Open it in two tabs. Then swap to `time.sleep(2)` inside `async def` and compare behavior.
4. Add a second router `blogapp` with `/blogapp/posts` and register it. Which line in `main.py` did you have to touch? (Answer: only one `include_router`, same as Django `INSTALLED_APPS` + urls.)

---

### **12. Cheat Sheet**

```
Create env        : python -m venv .venv
Install           : pip install "fastapi[standard]"
Run dev           : fastapi dev main.py
Run uvicorn       : uvicorn main:app --reload --port 8000
Docs              : /docs  /redoc  /openapi.json
Create app        : mkdir testapp + __init__.py + router.py
Register app      : app.include_router(router)
View              : @router.get("/path") def fn(): return {...}
Path param        : "/items/{item_id}"  + fn(item_id: int)
Query param       : fn(q: str | None = None)
Body              : fn(payload: PydanticModel)
Status code       : @router.post(..., status_code=201)
Error             : raise HTTPException(404, "msg")
Raw request       : fn(request: Request)
HTML response     : response_class=HTMLResponse
Dependency        : fn(x = Depends(func))
Tests             : TestClient(app) + pytest
Migrations        : Alembic (not built in)
```