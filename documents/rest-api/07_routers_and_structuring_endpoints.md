# 07 - Routers, APIRouter, and Structuring Endpoints in FastAPI

**Series context:** `01_REST_fundamentals` → `02_soap_vs_rest` → `03_fastapi_introduction` → `04_pydantic_v2` → `05_crud_with_sqlmodel` → `06_serialization_validation` → **you are here**

---

## What this file covers

How to split a FastAPI application into multiple files using `APIRouter`, how to share dependencies across routers, how to structure endpoints for full CRUD and complex operations, and how to handle API versioning.

---

## APIRouter — The Core Building Block

`APIRouter` lets you define route functions in a separate module and register them on the main `FastAPI` app with a shared `prefix` and `tags`. Think of it as a mini FastAPI application that gets mounted on the main one.

### Basic router setup

```python
# routers/courses.py

from fastapi import APIRouter

router = APIRouter(
    prefix="/courses",
    tags=["courses"],
)

@router.get("/")
def list_courses():
    return {"msg": "list of courses"}

@router.post("/")
def create_course():
    return {"msg": "course created"}

@router.get("/{course_id}")
def get_course(course_id: int):
    return {"msg": f"course {course_id}"}

@router.put("/{course_id}")
def update_course(course_id: int):
    return {"msg": f"course {course_id} updated"}

@router.patch("/{course_id}")
def partial_update_course(course_id: int):
    return {"msg": f"course {course_id} partially updated"}

@router.delete("/{course_id}")
def delete_course(course_id: int):
    return {"msg": f"course {course_id} deleted"}
```

### Registering the router on the app

```python
# main.py

from fastapi import FastAPI
from routers.courses import router as course_router

app = FastAPI()
app.include_router(course_router)
```

This produces the following URL patterns automatically:

```
GET    /courses/
POST   /courses/
GET    /courses/{course_id}
PUT    /courses/{course_id}
PATCH  /courses/{course_id}
DELETE /courses/{course_id}
```

No manual URL pattern definitions. No regex. The path is declared on the decorator.

---

## Full Control Route Functions

For complex operations — aggregating from multiple data sources, calling external services, non-standard response shapes — write the logic directly in the route function. You have complete control.

```python
# routers/reports.py

import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/course-summary/{course_id}")
async def course_summary(course_id: int):
    async with httpx.AsyncClient() as client:
        course_resp    = await client.get(f"http://internal-api/courses/{course_id}")
        enrollments    = await client.get(f"http://internal-api/enrollments/course/{course_id}")

    course_data     = course_resp.json()
    enrollment_data = enrollments.json()

    return {
        "course"     : course_data,
        "enrollments": enrollment_data["count"],
        "summary"    : f"{course_data['title']} has {enrollment_data['count']} active students"
    }
```

When to write route functions this way:
- Aggregating data from multiple internal or external APIs
- Non-standard response shapes (dashboard endpoints, analytics)
- Complex conditional logic across data sources
- Orchestration endpoints that coordinate multiple operations

---

## Full CRUD Router with SQLModel

The examples below use a **course platform** domain: courses with title, instructor, price, and category.

```python
# routers/courses.py

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from database import get_session
from models import Course
from schemas import CourseCreate, CourseRead, CourseUpdate

router     = APIRouter(prefix="/courses", tags=["courses"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/", response_model=list[CourseRead])
def list_courses(
    session : SessionDep,
    offset  : int = Query(default=0, ge=0),
    limit   : int = Query(default=100, le=100),
):
    return session.exec(select(Course).offset(offset).limit(limit)).all()


@router.get("/{course_id}", response_model=CourseRead)
def get_course(course_id: int, session: SessionDep):
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/", response_model=CourseRead, status_code=201)
def create_course(data: CourseCreate, session: SessionDep):
    course = Course.model_validate(data)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@router.put("/{course_id}", response_model=CourseRead)
def update_course(course_id: int, data: CourseCreate, session: SessionDep):
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    # PUT replaces the entire resource — all fields required
    course.sqlmodel_update(data.model_dump())
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@router.patch("/{course_id}", response_model=CourseRead)
def partial_update_course(course_id: int, data: CourseUpdate, session: SessionDep):
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    # PATCH only applies fields that were actually sent
    course.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, session: SessionDep):
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    session.delete(course)
    session.commit()
```

`PUT` vs `PATCH`: use `PUT` only when the client must send the complete resource. Use `PATCH` with `exclude_unset=True` for partial updates.

---

## Filtering with Query Parameters

Query params are declared directly as function parameters. No method override, no filter class needed.

```python
from typing import Optional

@router.get("/", response_model=list[CourseRead])
def list_courses(
    session   : SessionDep,
    title     : Optional[str] = Query(default=None, description="Filter by title (case-insensitive)"),
    instructor: Optional[str] = Query(default=None, description="Filter by instructor name"),
    category  : Optional[str] = Query(default=None),
    offset    : int           = Query(default=0, ge=0),
    limit     : int           = Query(default=100, le=100),
):
    statement = select(Course)
    if title is not None:
        statement = statement.where(Course.title.ilike(f"%{title}%"))
    if instructor is not None:
        statement = statement.where(Course.instructor.ilike(f"%{instructor}%"))
    if category is not None:
        statement = statement.where(Course.category == category)
    statement = statement.offset(offset).limit(limit)
    return session.exec(statement).all()
```

Usage:
```
GET /courses/                          → all courses
GET /courses/?title=python             → courses where title contains "python"
GET /courses/?instructor=Rohit         → courses by instructor Rohit
GET /courses/?category=backend&limit=5 → first 5 backend courses
```

FastAPI documents all query params in `/docs` automatically. No extra configuration needed.

---

## Shared Dependencies — get_or_404 Pattern

When multiple routes need the same "fetch + 404 check" logic, extract it into a dependency function. FastAPI caches the result within the request scope — if the same dependency is called multiple times in one request chain, it runs only once.

```python
# dependencies.py

from typing import Annotated
from fastapi import Depends, HTTPException
from sqlmodel import Session
from database import get_session
from models import Course


def get_course_or_404(
    course_id: int,
    session  : Session = Depends(get_session),
) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


# Reusable type alias
CourseDep  = Annotated[Course,  Depends(get_course_or_404)]
SessionDep = Annotated[Session, Depends(get_session)]
```

```python
# routers/courses.py

@router.get("/{course_id}", response_model=CourseRead)
def get_course(course: CourseDep):
    return course  # already fetched and 404-checked


@router.patch("/{course_id}", response_model=CourseRead)
def partial_update_course(course: CourseDep, data: CourseUpdate, session: SessionDep):
    course.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(course: CourseDep, session: SessionDep):
    session.delete(course)
    session.commit()
```

The fetch-and-validate logic is written once and injected wherever it's needed.

---

## Shared CRUD Utility Functions

For logic that isn't a dependency but is reused across routers, extract it into a `crud.py` module.

```python
# crud.py

from typing import Optional
from sqlmodel import Session, select
from models import Course
from schemas import CourseCreate, CourseUpdate


def get_all_courses(
    session   : Session,
    title     : Optional[str] = None,
    instructor: Optional[str] = None,
    offset    : int = 0,
    limit     : int = 100,
) -> list[Course]:
    stmt = select(Course)
    if title:
        stmt = stmt.where(Course.title.ilike(f"%{title}%"))
    if instructor:
        stmt = stmt.where(Course.instructor.ilike(f"%{instructor}%"))
    return session.exec(stmt.offset(offset).limit(limit)).all()


def create_course(session: Session, data: CourseCreate) -> Course:
    course = Course.model_validate(data)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


def partial_update_course(session: Session, course: Course, data: CourseUpdate) -> Course:
    course.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(course)
    session.commit()
    session.refresh(course)
    return course
```

---

## Router-Level Dependencies

Apply a dependency to every route in a router without repeating it on each decorator. This is the standard pattern for authentication.

```python
from fastapi import APIRouter, Depends
from auth import verify_token

# Every route in this router requires a valid token
router = APIRouter(
    prefix     = "/courses",
    tags       = ["courses"],
    dependencies = [Depends(verify_token)],
)
```

You can also compose router-level and endpoint-level dependencies. The pattern is to have a more specific dependency depend on the shared one:

```python
def get_current_user(token: str = Depends(oauth2_scheme)):
    # validate token, return user
    ...

def require_instructor(user: User = Depends(get_current_user)):
    if user.role != "instructor":
        raise HTTPException(status_code=403, detail="Instructor access required")
    return user

# Router-level: all routes require a logged-in user
router = APIRouter(prefix="/courses", dependencies=[Depends(get_current_user)])

# Endpoint-level: only instructors can create
@router.post("/", response_model=CourseRead, status_code=201)
def create_course(data: CourseCreate, _: User = Depends(require_instructor), session: SessionDep):
    ...
```

---

## Nested Routers

`include_router` works on `APIRouter` instances too, not just the main `FastAPI` app. This lets you compose routers hierarchically.

```python
# routers/api.py  — aggregate all v1 routers

from fastapi import APIRouter
from routers import courses, enrollments, instructors

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(courses.router)
api_router.include_router(enrollments.router)
api_router.include_router(instructors.router)
```

```python
# main.py

from fastapi import FastAPI
from routers.api import api_router

app = FastAPI()
app.include_router(api_router)
```

Final URL structure:
```
/api/v1/courses/
/api/v1/courses/{id}
/api/v1/enrollments/
/api/v1/instructors/
```

---

## API Versioning

`include_router` accepts an optional `prefix` argument that overrides or extends the router's own prefix. This is the standard way to support multiple API versions simultaneously.

```python
# main.py

from fastapi import FastAPI
from routers import courses_v1, courses_v2

app = FastAPI(title="Course Platform API")

# Both versions live on the same app
app.include_router(courses_v1.router, prefix="/api/v1")
app.include_router(courses_v2.router, prefix="/api/v2")
```

```python
# routers/courses_v1.py

from fastapi import APIRouter
router = APIRouter(prefix="/courses", tags=["courses-v1"])

@router.get("/{course_id}")
def get_course(course_id: int):
    return {"id": course_id, "title": "FastAPI Fundamentals"}
```

```python
# routers/courses_v2.py — richer response shape

from fastapi import APIRouter
router = APIRouter(prefix="/courses", tags=["courses-v2"])

@router.get("/{course_id}")
def get_course(course_id: int):
    return {
        "data"   : {"id": course_id, "title": "FastAPI Fundamentals"},
        "version": "v2",
        "total"  : 1,
    }
```

This produces:
```
GET /api/v1/courses/{id}   → original response shape
GET /api/v2/courses/{id}   → enriched response shape with metadata
```

To deprecate an old version, mark it at include time:

```python
app.include_router(courses_v1.router, prefix="/api/v1", deprecated=True)
```

This marks all v1 routes as deprecated in the `/docs` UI automatically.

---

## Multiple Routers on One App

```python
# main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel
from database import engine
from routers import courses, enrollments, instructors, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Course Platform API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(enrollments.router)
app.include_router(instructors.router)
```

Each router has its own prefix and tags. The final URL structure:

```
/auth/login
/auth/logout
/courses/
/courses/{id}
/enrollments/
/enrollments/{id}
/instructors/
/instructors/{id}
```

---

## Application Structure Summary

```mermaid
flowchart TD
    A[main.py\nFastAPI app + lifespan] --> B[include_router courses]
    A --> C[include_router enrollments]
    A --> D[include_router auth]

    B --> E[routers/courses.py\nAPIRouter prefix=/courses]
    E --> F[GET /  list]
    E --> G[POST / create]
    E --> H[GET /{id} retrieve]
    E --> I[PUT /{id} full update]
    E --> J[PATCH /{id} partial update]
    E --> K[DELETE /{id} delete]

    H --> L[Depends get_course_or_404]
    I --> L
    J --> L
    K --> L

    F --> M[Depends get_session]
    G --> M
    L --> M

    M --> N[database.py\nSQLModel engine + Session]
```

---

## Project Layout: File-Type vs Domain-Grouped

### File-type layout (good for small projects)

```
app/
├── main.py
├── database.py
├── models.py         # all DB models
├── schemas.py        # all Pydantic schemas
├── crud.py           # all DB operations
├── dependencies.py   # all shared deps
└── routers/
    ├── courses.py
    ├── enrollments.py
    └── auth.py
```

### Domain-grouped layout (better for larger projects)

```
app/
├── main.py
├── database.py
├── courses/
│   ├── router.py
│   ├── models.py
│   ├── schemas.py
│   ├── crud.py
│   └── dependencies.py
├── enrollments/
│   ├── router.py
│   ├── models.py
│   ├── schemas.py
│   └── crud.py
└── auth/
    ├── router.py
    └── dependencies.py
```

Domain-grouped scales better: adding a new feature means adding a new folder, not editing shared files. File-type layout is simpler and fine for APIs with fewer than ~5 domains.

---

## Key Points

- `APIRouter` is the building block for modular FastAPI apps. Declare routes on it, register it on the app with `include_router`.
- URL patterns are declared on route decorators. No regex, no separate URL config file.
- Filtering and pagination are query parameters declared directly as function parameters.
- The `get_or_404` pattern — a dependency that fetches a resource and raises `404` if missing — eliminates repeated fetch logic across GET, PATCH, and DELETE handlers.
- Router-level `dependencies=[Depends(...)]` applies auth or cross-cutting concerns to all routes without repeating it on each decorator.
- FastAPI caches dependency results within a request's scope by default — the same dependency called multiple times in one request chain runs only once.
- API versioning is done by passing a `prefix` override to `include_router`. Multiple versions of the same router can coexist on one app.
- `PUT` requires the full resource payload from the client. `PATCH` with `exclude_unset=True` is correct for partial updates. Never use `PUT` for partial updates.
- Choose file-type layout for small projects, domain-grouped layout once your API has more than 4–5 resource types.

---

Next: [08_authentication_and_dependencies.md](./08_authentication_and_dependencies.md)