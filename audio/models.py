import uuid
from sqlmodel import SQLModel,Field


class audiot(SQLModel,table = True):
    __tablename__ = 'audiot'
    job_id: str = Field( primary_key=True)
    source_file : str = Field(nullable=False)
    status : str = Field(nullable=False)
    report : str = Field(nullable=True)
    model_ai : str = Field(nullable=True)


class history(SQLModel,table = True):
    __tablename__ = 'history'
    job_id: str = Field(primary_key=True)
    source_file: str = Field(nullable=False)
    status: str = Field(nullable=False)
    report: str = Field(nullable=True)
    model_ai: str = Field(nullable=True)


