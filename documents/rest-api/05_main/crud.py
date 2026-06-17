
from typing import Optional
from sqlmodel import Session, select
from models import Employee
from schemas import EmployeeCreate, EmployeeUpdate


def get_employee(session: Session, employee_id: int) -> Optional[Employee]:
    return session.get(Employee, employee_id)


def get_employees(session: Session, offset: int = 0, limit: int = 100)->list[Employee]:
    statement = select(Employee).offset(offset).limit(limit)
    return session.exec(statement).all() #type: ignore


def create_employee(session: Session, emplyoee_id: int, data: EmployeeUpdate) -> Optional[Employee]:
    emp = Employee.model_validate(data)
    session.add(emp)
    session.commit()
    session.refresh(emp)
    return emp


def update_employee(session: Session, employee_id: int, data: EmployeeUpdate) -> Optional[Employee]:
    emp = session.get(Employee, employee_id)
    if emp is None:
        return None
    
    update_data = data.model_dump(exclude_unset=True)
    emp.sqlmodel_update(update_data)
    session.add(emp)
    session.commit()
    session.refresh(emp)
    return emp 


def delete_employee(session: Session, employee_id: int)-> bool:
    emp = session.get(Employee, employee_id)
    if emp is None:
        return False
    session.delete(emp)
    session.commit()
    return True

