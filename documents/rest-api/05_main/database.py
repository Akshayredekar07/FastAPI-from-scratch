
from sqlmodel import create_engine, SQLModel, Session

DATABASE_URL = "sqlite:///./employees.db"


engine = create_engine(DATABASE_URL,connect_args={"check_same_thread": False}, echo=True)


def create_db_and_table():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


