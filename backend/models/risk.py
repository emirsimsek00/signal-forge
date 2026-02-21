"""Risk assessment model — stores computed risk scores and explanations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from backend.database import Base


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, default="default")
    signal_id: Mapped[int] = mapped_column(Integer, index=True)
    composite_score: Mapped[float] = mapped_column(Float)
    sentiment_component: Mapped[float] = mapped_column(Float, default=0.0)
    anomaly_component: Mapped[float] = mapped_column(Float, default=0.0)
    ticket_volume_component: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_component: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_component: Mapped[float] = mapped_column(Float, default=0.0)
    tier: Mapped[str] = mapped_column(String(20), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class RiskOverview(BaseModel):
    average_score: float
    critical_count: int
    high_count: int
    moderate_count: int
    low_count: int
    total_signals: int
    trend: str  # "rising", "stable", "falling"
    top_risks: list[dict]


class RiskHeatmapCell(BaseModel):
    source: str
    hour: int
    score: float
    tier: str
    count: int
