import uuid
from sqlmodel import SQLModel,Field


class audiot(SQLModel,table = True):
    __tablename__ = 'audiot'
    job_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_file : str = Field(nullable=False)
    status : str = Field(nullable=False)
    report : str = Field(nullable=True)
    model_ai : str = Field(nullable=True)

