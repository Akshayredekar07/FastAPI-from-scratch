
from contextlib import asynccontextmanager 
from fastapi import FastAPI 
from database import create_db_and_table
from routers.employees import router as employee_router 


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_table()
    yield


app = FastAPI(title="Eployee API", lifespan=lifespan)
app.include_router(employee_router)