"""Notification models — preferences and delivery log."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from backend.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # "email" | "slack"
    target: Mapped[str] = mapped_column(String(500))   # email addr or webhook URL
    triggers: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    trigger: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))  # "sent" | "failed"
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ── Pydantic Schemas ─────────────────────────────────────────

class NotificationPreferenceCreate(BaseModel):
    channel: str  # "email" | "slack"
    target: str
    triggers: list[str] = ["critical_signal", "incident_created"]


class NotificationPreferenceResponse(BaseModel):
    id: int
    tenant_id: str
    channel: str
    target: str
    triggers: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogResponse(BaseModel):
    id: int
    channel: str
    trigger: str
    subject: str
    status: str
    error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
