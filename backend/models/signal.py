"""Signal data model — the core entity of SignalForge."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from backend.database import Base


class SignalSource(str, enum.Enum):
    REDDIT = "reddit"
    NEWS = "news"
    ZENDESK = "zendesk"
    STRIPE = "stripe"
    PAGERDUTY = "pagerduty"
    SYSTEM = "system"
    FINANCIAL = "financial"
    CUSTOM = "custom"


class RiskTier(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# ─── SQLAlchemy Model ────────────────────────────────────────────


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, default="default")
    source: Mapped[str] = mapped_column(String(50), index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # NLP-derived fields
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    urgency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    entities_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Risk
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    risk_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )


# ─── Pydantic Schemas ────────────────────────────────────────────


class SignalCreate(BaseModel):
    source: str
    source_id: str | None = None
    title: str | None = None
    content: str
    timestamp: datetime
    metadata_json: str | None = None


class SignalResponse(BaseModel):
    id: int
    source: str
    source_id: str | None = None
    title: str | None = None
    content: str
    timestamp: datetime
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    urgency: str | None = None
    entities_json: str | None = None
    summary: str | None = None
    risk_score: float | None = None
    risk_tier: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalListResponse(BaseModel):
    signals: list[SignalResponse]
    total: int
    page: int
    page_size: int
