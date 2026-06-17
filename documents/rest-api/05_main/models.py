
from typing import Optional
from sqlmodel import Field, SQLModel


class Employee(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    eno: int 
    ename: str = Field(max_length=64)
    esal: float
    eaddr: str = Field(max_length=128)

