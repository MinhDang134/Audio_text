import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional,List


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


class session_chat(SQLModel,table = True):
    __tablename__ = 'session_chat'
    session_id: str = Field(primary_key=True, index=True)


    messages: List["ChatMessage"] = Relationship(back_populates="chat_session")

class ChatMessage(SQLModel, table=True):
    __tablename__ = 'chat_messages'
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session_chat.session_id", index=True)
    sender: str = Field(nullable=False)
    message_text: str = Field(nullable=False)
    timestamp: float = Field(nullable=False)

    # Định nghĩa mối quan hệ ngược lại
    chat_session: Optional[session_chat] = Relationship(back_populates="messages")
