
from typing import Optional
from sqlmodel import SQLModel

class EmployeeBase(SQLModel):
    eno: int    
    ename: str 
    esal: float
    eaddr: str 


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeRead(EmployeeBase):
    id: int


class EmployeeUpdate(SQLModel):
    eno: Optional[int] = None
    ename: Optional[str] = None
    esal: Optional[float] = None
    eaddr: Optional[str] = None