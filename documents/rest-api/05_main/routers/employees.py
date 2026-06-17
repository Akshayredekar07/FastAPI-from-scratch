
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from database import get_session
from schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate
import crud as crud 

router = APIRouter(prefix="/employees", tags=["employees"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/", response_model=list[EmployeeRead])
def list_employees(
    session: SessionDep,
    offset: int = Query(default=0, gt=0),
    limit: int = Query(default=100, le=100),
):
    return crud.get_employees(session, offset=offset, limit=limit)



@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(employee_id: int, session: SessionDep):
    emp = crud.get_employee(session, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    


@router.post("/", response_model=EmployeeRead, status_code=201)
def create_employee(data: EmployeeCreate, session: SessionDep):
    return crud.create_employee(session, data) #type: ignore


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(employee_id: int, data: EmployeeUpdate, session: SessionDep):
    emp = crud.update_employee(session, employee_id, data)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@router.delete("/{employee_id}", response_model=EmployeeRead)
def delete_employee(employee_id: int, session: SessionDep):
    deleted = crud.delete_employee(session, employee_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Employee not found")