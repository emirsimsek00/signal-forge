"""Incident notes model for collaboration features."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from backend.database import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, default="default")
    incident_id: Mapped[int] = mapped_column(Integer, index=True)
    content: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(100), default="System")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class NoteCreate(BaseModel):
    content: str
    author: str = "User"


class NoteResponse(BaseModel):
    id: int
    incident_id: int
    content: str
    author: str
    created_at: datetime

    model_config = {"from_attributes": True}
