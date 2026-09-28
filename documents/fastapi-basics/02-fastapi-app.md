# **FastAPI**

Every section mirrors your Django notes (project, app, views, urls, multiple apps, templates) with the FastAPI equivalent. Type every snippet yourself and run it.

---

## 0. Read this first: where the Django analogy breaks

| Django assumption | FastAPI reality |
|---|---|
| "Batteries included" (ORM, admin, auth, templates, forms) | Minimal core. Routing + validation + docs. ORM, admin, auth are your choice (SQLAlchemy/SQLModel, etc.) |
| MVT architecture is enforced | No enforced architecture. You choose the structure |
| Built for HTML pages first | Built for **JSON APIs** first. HTML templates work but are secondary |
| `manage.py startproject/startapp` scaffolding | No scaffolding. You create files and folders by hand |
| View function must accept `request` | Function takes only what it declares (path params, query params, body). `request` is optional |
| Return `HttpResponse` | Return a `dict`/Pydantic model, FastAPI converts to JSON |
| `urls.py` central routing | Decorators on the function: `@app.get("/hello")` |
| App = reusable unit registered in `INSTALLED_APPS` | No registry. A "module" is just an `APIRouter` you include |
| Server restart not needed (autoreload) | Same, with `fastapi dev` |
| Built-in SQL injection/XSS/CSRF protection via ORM/templates | No ORM shipped, so SQL injection safety is on you (use parameterized queries/ORM). Jinja2 templates autoescape HTML by default. CSRF matters only for cookie-based sessions, not token-based APIs |

Consequence: "project = application + configuration" does not exist here. There is one `FastAPI()` instance, and you organize routers however you like.

---

## 1. Environment setup

```bash
mkdir fastproject && cd fastproject
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install "fastapi[standard]"
pip freeze > requirements.txt
```

`fastapi[standard]` installs FastAPI, Uvicorn, the `fastapi` CLI, Jinja2 (templates), and `python-multipart` (forms). Plain `pip install fastapi` gives you none of the server/CLI extras.

---

## 2. Django steps mapped to FastAPI steps

| Django step | FastAPI step |
|---|---|
| 1. `django-admin startproject` | Create folder + `main.py` |
| 2. `python manage.py startapp testapp` | Create folder `testapp/` with `__init__.py` and `router.py` |
| 3. Add to `INSTALLED_APPS` | `app.include_router(...)` in `main.py` |
| 4. Write view in `views.py` | Write path operation function in `router.py` |
| 5. `path("hello/", views.display)` in `urls.py` | `@router.get("/hello")` decorator |
| 6. `python manage.py runserver` | `fastapi dev main.py` |
| 7. Visit `http://127.0.0.1:8000/hello` | Same URL, plus free docs at `/docs` |

---

## 3. App 1: Just a welcome message

### File: `main.py`

```python
from fastapi import FastAPI

app = FastAPI(title="FirstProject")


@app.get("/hello")
def greeting():
    return {"message": "Welcome to FastAPI classes"}
```

Note: no `request` argument required. Django needed it; FastAPI does not.

### Run

```bash
fastapi dev main.py
# custom port (Django: runserver 7777)
fastapi dev main.py --port 7777
```

`fastapi dev` auto-reloads on file change (Django's autoreload equivalent). Unlike Django, if the port is busy it fails; it does not pick another.

### Send request

```bash
curl http://127.0.0.1:8000/hello
```

Or open in browser. Bonus, no Django equivalent without extra packages:

- `http://127.0.0.1:8000/docs` : Swagger UI (click "Try it out")
- `http://127.0.0.1:8000/redoc` : ReDoc

### Root path (Django: `path("", views.display)`)

```python
@app.get("/")
def home():
    return {"message": "Home"}
```

Visit `http://127.0.0.1:8000/`.

### Returning HTML (the Django `HttpResponse("<h1>...")` way)

```python
from fastapi.responses import HTMLResponse

@app.get("/html-hello", response_class=HTMLResponse)
def html_hello():
    return "<h1>Welcome to FastAPI classes</h1>"
```

Same downside you noted in Django: HTML inside Python hurts readability, mixes roles, and blocks reuse. Section 9 fixes it with templates.

---

## 4. App 2: Current server time

### File: `main.py`

```python
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/time")
def time_info_json():
    return {"server_time": datetime.now().isoformat()}


@app.get("/time-html", response_class=HTMLResponse)
def time_info_html():
    return f"<h1>Hello, current date and time: {datetime.now()}</h1>"
```

URLs: `/time` and `/time-html`. In Django notes your route was `datetime/` but you requested `/time`; that mismatch gives a 404. FastAPI behaves the same: the URL must match the decorator exactly.

---

## 5. App 3: Multiple views in one application

```python
@app.get("/first")
def first():
    return {"view": "first"}

@app.get("/second")
def second():
    return {"view": "second"}
```

Single file, multiple path operations. Inside one, you can call plain helper functions freely.

### Home page linking to other pages (Django notes: "end user needs only the home page URL")

```python
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>Home</h1>
    <a href="/time-html">Time</a> |
    <a href="/wish">Wish</a> |
    <a href="/docs">API docs</a>
    """
```

---

## 6. App 4: Message based on time of day

```python
from datetime import datetime

@app.get("/wish", response_class=HTMLResponse)
def wish():
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        msg = "Good Morning"
    elif hour < 16:
        msg = "Good Afternoon"
    elif hour < 21:
        msg = "Good Evening"
    else:
        msg = "Good Night"
    return f"<h1>Hello Friend, {msg}</h1><hr><h1>Server time: {now}</h1>"
```

JSON version:

```python
@app.get("/wish-json")
def wish_json():
    hour = datetime.now().hour
    msg = ("Good Morning" if hour < 12 else
           "Good Afternoon" if hour < 16 else
           "Good Evening" if hour < 21 else
           "Good Night")
    return {"greeting": f"Hello Friend, {msg}"}
```

`datetime.now()` is server-local time, not the user's. Fine for practice, wrong for real apps (use UTC + client timezone).

---

## 7. App 5: One project, multiple "apps" (routers)

In Django you split by app and `include()` app-level `urls.py`. In FastAPI the same idea is `APIRouter`.

### Structure

```
fastproject/
├── main.py
├── requirements.txt
├── firstapp/
│   ├── __init__.py
│   └── router.py
└── secondapp/
    ├── __init__.py
    └── router.py
```

### File: `firstapp/router.py`

```python
from fastapi import APIRouter

router = APIRouter(prefix="/firstapp", tags=["firstapp"])


@router.get("/test1")
def test_view1():
    return {"app": "first", "view": "test1"}


@router.get("/attendance")
def attendance():
    return {"app": "first", "view": "attendance"}
```

### File: `secondapp/router.py`

```python
from fastapi import APIRouter

router = APIRouter(prefix="/secondapp", tags=["secondapp"])


@router.get("/test2")
def test_view2():
    return {"app": "second", "view": "test2"}
```

### File: `main.py`

```python
from fastapi import FastAPI

from firstapp.router import router as first_router     # alias avoids name collision
from secondapp.router import router as second_router

app = FastAPI(title="OneProjectMultipleApps")

app.include_router(first_router)
app.include_router(second_router)
```

This is exactly your Django error scenario: both files export `router`. Importing both without aliases makes the second overwrite the first, the same as `views` overriding `views`. The `as first_router` fix is identical to `views as v1`.

### URLs

- `http://127.0.0.1:8000/firstapp/test1`
- `http://127.0.0.1:8000/firstapp/attendance`
- `http://127.0.0.1:8000/secondapp/test2`

### Mapping to your Django include notes

| Django | FastAPI |
|---|---|
| `path('testapp/', include('testapp.urls'))` | `app.include_router(router, prefix="/testapp")` or prefix on the `APIRouter` |
| App-level `urls.py` | `router.py` |
| Project-level `urls.py` stays clean | `main.py` stays clean |
| Reuse app across projects | Import the router in another project, or include one router inside another with `router.include_router(...)` |

Advantages you listed (reusability, clean root, maintainability) all hold. The prefix can also be given at include time, which lets you mount the same router at different paths:

```python
app.include_router(first_router, prefix="/v1")   # /v1/firstapp/test1
```

---

## 8. Passing data to views (not covered in your Django notes, needed in practice)

### Path parameter

```python
@router.get("/user/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}
```

`/user/5` works. `/user/abc` returns 422 automatically because of the `int` hint. Django needs `<int:user_id>` in the path plus manual handling.

### Query parameter

```python
@router.get("/search")
def search(q: str, limit: int = 10):
    return {"q": q, "limit": limit}
```

`/search?q=fastapi&limit=5`. `q` is required (no default), `limit` optional.

### Request body with Pydantic (replaces Django forms/serializers)

File: `testapp/schemas.py`

```python
from pydantic import BaseModel, Field

class StudentIn(BaseModel):
    name: str = Field(min_length=2)
    age: int = Field(ge=5, le=100)

class StudentOut(BaseModel):
    id: int
    name: str
```

File: `testapp/router.py`

```python
from fastapi import APIRouter
from .schemas import StudentIn, StudentOut

router = APIRouter(prefix="/testapp", tags=["students"])

@router.post("/students", response_model=StudentOut, status_code=201)
def create_student(payload: StudentIn):
    # fake save
    return {"id": 1, "name": payload.name, "age": payload.age}   # age is filtered out by response_model
```

Test via `/docs` or:

```bash
curl -X POST http://127.0.0.1:8000/testapp/students \
  -H "Content-Type: application/json" \
  -d '{"name": "Karan", "age": 21}'
```

`response_model` strips fields not in `StudentOut`. That is a real safety feature (do not leak password hashes), and it is the closest thing to a Django serializer.

### Errors

```python
from fastapi import HTTPException

@router.get("/students/{sid}")
def get_student(sid: int):
    if sid != 1:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"id": 1, "name": "Karan"}
```

---

## 9. Templates (Django's "T" in MVT)

Your Django note: views hold business logic, templates hold presentation logic. Same separation in FastAPI via Jinja2.

### Correcting a claim from your notes

You wrote the Django template tag syntax is "jinja2 syntax". It is **Django Template Language (DTL)**, which looks similar to Jinja2 but is a different engine. FastAPI actually uses **real Jinja2**. `{{ msg }}` and `{% if %}` work in both. Differences show up in filters, function calls (`{{ msg.strftime('%Y') }}` works in Jinja2, not in DTL), and some tag names.

### Structure

```
templateproject/
├── main.py
├── templates/
│   └── templateapp/
│       ├── wish.html
│       └── datetime.html
└── static/
    └── style.css
```

Mirrors Django's `templates/<appname>/file.html` convention. In FastAPI the subfolder is optional but keeps names from colliding across apps.

### Step 1: Build the template path programmatically (not hard-coded)

Your Django notes reject a hard-coded `C:\Users\...` path and use `BASE_DIR = Path(__file__).resolve().parent.parent`. Same principle here.

File: `main.py`

```python
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent      # main.py is in the project root, so .parent (not .parent.parent)
TEMPLATE_DIR = BASE_DIR / "templates"

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATE_DIR)
```

Path recap from your pathlib notes:

| Expression | Result |
|---|---|
| `Path(__file__)` | Path object, possibly relative |
| `.resolve()` | Absolute path |
| `.resolve().parent` | Folder containing the file |
| `.resolve().parent.parent` | One level higher (Django needs this because `settings.py` is nested inside the inner project folder) |

### Step 2: Create the HTML file

File: `templates/templateapp/wish.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Templates for FastAPI</title>
</head>
<body>
    <h1>Welcome to the 2nd hero of FastAPI: Templates</h1>
</body>
</html>
```

### Step 3: View function returning the template

```python
@app.get("/hello", response_class=HTMLResponse)
def wish_view(request: Request):
    return templates.TemplateResponse(request, "templateapp/wish.html")
```

Unlike a plain path operation, `request: Request` **is required** here: the template engine needs it. That is the one place FastAPI matches Django's "request must be passed" rule.

The older signature `TemplateResponse("name.html", {"request": request})` still works in some versions but is deprecated. Use `(request, name, context)`.

### Step 4: Inject dynamic content (template variables)

File: `templates/templateapp/datetime.html`

```html
<!DOCTYPE html>
<html>
<body>
    <h1>Current server date and time</h1>
    <p>{{ msg }}</p>
    <p>Formatted: {{ msg.strftime("%d %b %Y, %H:%M") }}</p>
</body>
</html>
```

File: `main.py`

```python
@app.get("/datetime", response_class=HTMLResponse)
def datetime_view(request: Request):
    context = {"msg": datetime.now()}
    return templates.TemplateResponse(request, "templateapp/datetime.html", context)
```

Django equivalents you listed as "also acceptable":

| Django | FastAPI |
|---|---|
| `render(request, 'Ta/datetime.html', context=my_dict)` | `templates.TemplateResponse(request, "Ta/datetime.html", context=my_dict)` |
| `render(request, 'Ta/datetime.html', my_dict)` | `templates.TemplateResponse(request, "Ta/datetime.html", my_dict)` |
| `render(request, 'Ta/datetime.html', {"msg": date})` | `templates.TemplateResponse(request, "Ta/datetime.html", {"msg": date})` |

Your note has a typo in the last Django example: `'Ta/datetime.html` is missing the closing quote. Same bug in FastAPI is a `SyntaxError`.

"Rendering" = converting the template + context into an HTTP response, as in your notes.

### Step 5: Loops and conditions

File: `templates/templateapp/students.html`

```html
<h1>Students</h1>
<ul>
{% for s in students %}
    <li>{{ s.name }} ({{ s.age }})
        {% if s.age >= 18 %}adult{% else %}minor{% endif %}
    </li>
{% endfor %}
</ul>
```

```python
@app.get("/students-page", response_class=HTMLResponse)
def students_page(request: Request):
    students = [
        {"name": "Karan", "age": 21},
        {"name": "Tanvi", "age": 17},
    ]
    return templates.TemplateResponse(request, "templateapp/students.html", {"students": students})
```

### Step 6: Template inheritance (base layout)

File: `templates/base.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My Site{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='style.css') }}">
</head>
<body>
    <nav><a href="/">Home</a></nav>
    {% block content %}{% endblock %}
</body>
</html>
```

File: `templates/templateapp/home.html`

```html
{% extends "base.html" %}
{% block title %}Home{% endblock %}
{% block content %}
    <h1>Hello {{ name }}</h1>
{% endblock %}
```

### Step 7: Static files (CSS/JS/images)

File: `main.py`

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
```

File: `static/style.css`

```css
body { font-family: sans-serif; }
```

The folder must exist or the app crashes at startup.

### Security note

Jinja2Templates autoescapes `.html` templates, so `{{ user_input }}` is escaped (XSS protection, like Django). Using `{{ x | safe }}` disables that; avoid it on user data.

---

## 10. Recommended structure once things grow

```
fastproject/
├── main.py                    # creates app, includes routers, mounts static
├── core/
│   ├── __init__.py
│   └── templating.py          # BASE_DIR, TEMPLATE_DIR, templates = Jinja2Templates(...)
├── firstapp/
│   ├── __init__.py
│   ├── router.py              # views (path operations)
│   └── schemas.py             # Pydantic models
├── secondapp/
│   ├── __init__.py
│   └── router.py
├── templates/
│   ├── base.html
│   └── firstapp/
│       └── home.html
├── static/
│   └── style.css
└── requirements.txt
```

File: `core/templating.py`

```python
from pathlib import Path
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent   # core/ is one level down, so two parents
templates = Jinja2Templates(directory=BASE_DIR / "templates")
```

Routers then do `from core.templating import templates`. One shared instance, no repeated path logic.

---

## 11. Django to FastAPI cheat sheet

| Concept | Django | FastAPI |
|---|---|---|
| Create project | `django-admin startproject X` | Make folder + `main.py` |
| Create app | `python manage.py startapp a` | Make `a/router.py` |
| Register app | `INSTALLED_APPS` | `app.include_router(a_router)` |
| Run server | `python manage.py runserver` | `fastapi dev main.py` |
| Production run | gunicorn/uvicorn + `wsgi.py`/`asgi.py` | `fastapi run main.py` or `uvicorn main:app` |
| Route | `path("x/", views.f)` | `@router.get("/x")` |
| Include sub-routes | `include('a.urls')` | `include_router(router, prefix=...)` |
| Return text/HTML | `HttpResponse(s)` | `HTMLResponse` or `response_class=HTMLResponse` |
| Return JSON | `JsonResponse(d)` | return a `dict` |
| Templates | `render(request, ...)` | `templates.TemplateResponse(request, ...)` |
| Template dir config | `TEMPLATES["DIRS"]` | `Jinja2Templates(directory=...)` |
| Static files | `STATICFILES_DIRS` | `app.mount("/static", StaticFiles(...))` |
| Config file | `settings.py` | Your own `config.py` / `pydantic-settings` |
| DB models | `models.py` + ORM | SQLAlchemy / SQLModel |
| Migrations | `makemigrations`, `migrate` | Alembic |
| Admin | built-in | None built in (third-party options exist) |
| Forms/validation | Forms/serializers | Pydantic models |
| Built-in docs | none (needs DRF add-ons) | `/docs`, `/redoc` automatic |
| Async | Supported, partial | First class (`async def`) |
| `wsgi.py` / `asgi.py` | Present | Not needed, `app` is the ASGI app |

---

## 12. `def` vs `async def`

```python
@app.get("/sync")
def sync_view():            # runs in a threadpool, safe for blocking code (requests, sync DB drivers)
    return {"ok": True}

@app.get("/async")
async def async_view():     # runs on the event loop, use only with awaitable libs (httpx, asyncpg)
    return {"ok": True}
```

Common mistake: `async def` with a blocking call inside (e.g. `time.sleep`, `requests.get`). That freezes the whole server. If unsure, use plain `def`.

---

## 13. Practice exercises (mirrors your Django "app-1 to app-5")

1. **app-1**: `/welcome` returns a welcome message.
2. **app-2**: `/time` returns server time as JSON and `/time-html` as HTML.
3. **app-3**: Three routes in one router: `/a`, `/b`, `/c`.
4. **app-4**: `/wish` returns greeting by hour. Add `?name=Karan` as a query parameter and include it in the message.
5. **app-5**: Two routers (`firstapp`, `secondapp`) with different prefixes, both included in `main.py`. Deliberately import both as `router` and observe the bug, then fix with aliases.
6. **templates-1**: Move the wish HTML into `templates/wishapp/wish.html`.
7. **templates-2**: Pass the current time, greeting, and a list of 3 tasks to the template. Render with `for` and `if`.
8. **templates-3**: Add `base.html` and make two pages extend it, with a shared CSS file from `/static`.
9. **beyond Django notes**: `POST /students` with a Pydantic model and `response_model`; break validation on purpose and read the 422 body.

---

## 14. Corrections to your Django notes (worth fixing before you rely on them)

| In your notes | Problem |
|---|---|
| `from django.url import path` | Module is `django.urls` |
| `from testapp import view` / `views.display` | File is `views.py`, so `from testapp import views` |
| `urlpatterns[ ... ]` | Needs `=`: `urlpatterns = [ ... ]` |
| View body `<h1>...</h1>` on its own line, then `HttpResponse(s)` | `s` is never defined; the HTML must be assigned to a string |
| MVT: "C: Controller (presentation logic, html file)" | Wrong. In MVT the **Template** is the presentation layer. Django itself (URL dispatcher + framework) plays the Controller role |
| "Template tags known as template variables" | Different things. `{{ x }}` is a **variable**, `{% ... %}` is a **tag** |
| "DIRS: ['C:\Users\...']" | Backslashes in normal strings break (`\U` is an escape). Another reason to use `Path` |
| Step 3 in the Jobsapp block adds `"testapp"` | Should be `"Jobsapp"` |
| `urls.py` "name not need... but recommended" | App-level `urls.py` is a **required** convention for `include()` to work, not optional |
| SQL injection example | Django's ORM parameterizes queries, that is why it's safe. Raw string-built SQL is still vulnerable in Django, and in FastAPI |

---

## 15. Where to go next

1. Database: SQLModel or SQLAlchemy 2.x + Alembic migrations (replaces Django ORM and migrations)
2. Dependency injection with `Depends()` (DB sessions, auth, shared params). This is the biggest FastAPI idea with no Django twin
3. Authentication: OAuth2 password flow + JWT, per the official tutorial
4. Background tasks, middleware, CORS
5. Testing with `TestClient` (from `fastapi.testclient`)
6. Lifespan events for startup/shutdown (loading models, DB pools). Directly relevant to serving LLM/RAG pipelines: load the embedding model once at startup, not per request

Official docs: https://fastapi.tiangolo.com