"""Incident data model — groups correlated signals into incidents."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from backend.database import Base


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, enum.Enum):
    ACTIVE = "active"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    related_signal_ids_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class IncidentCreate(BaseModel):
    title: str
    description: str
    severity: str = "medium"
    start_time: datetime
    end_time: datetime | None = None
    related_signal_ids: list[int] = []
    root_cause_hypothesis: str | None = None


class IncidentResponse(BaseModel):
    id: int
    title: str
    description: str
    severity: str
    status: str
    start_time: datetime
    end_time: datetime | None = None
    related_signal_ids_json: str | None = None
    root_cause_hypothesis: str | None = None
    recommended_actions: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
