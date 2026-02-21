"""User data model for authentication — synced from Supabase Auth."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supabase_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Pydantic Schemas ─────────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    supabase_id: str
    tenant_id: str
    email: str
    display_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
