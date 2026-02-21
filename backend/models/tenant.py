"""Tenant (organization) model for multi-tenancy."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from backend.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


# ── Pydantic Schemas ─────────────────────────────────────────

class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}
