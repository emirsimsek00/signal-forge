"""Async SQLAlchemy database engine and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

# Detect database backend and configure accordingly
_is_postgres = "postgresql" in settings.database_url

_engine_kwargs: dict = {"echo": False}
if _is_postgres:
    # PostgreSQL connection pool settings
    _engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables."""
    # Ensure model modules are imported so SQLAlchemy metadata is populated.
    from backend.models import signal, incident, risk  # noqa: F401
    from backend.models import user  # noqa: F401
    from backend.models import note  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """Dependency yielding an async DB session."""
    async with async_session() as session:
        yield session

