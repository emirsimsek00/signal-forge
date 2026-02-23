"""Async SQLAlchemy database engine and session management."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from backend.config import settings

# Detect database backend and configure accordingly
_is_postgres = "postgresql" in settings.database_url
_is_supabase_pooler = "pooler.supabase.com" in settings.database_url and "asyncpg" in settings.database_url

_engine_kwargs: dict = {"echo": False}
if _is_postgres:
    # PostgreSQL connection pool settings
    _engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    })

if _is_supabase_pooler:
    # Supabase pooler runs PgBouncer in transaction/statement pooling modes.
    # Use NullPool and unique prepared statement names to avoid collisions.
    _engine_kwargs.pop("pool_size", None)
    _engine_kwargs.pop("max_overflow", None)
    _engine_kwargs.pop("pool_pre_ping", None)
    _engine_kwargs.pop("pool_recycle", None)
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = {
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        "statement_cache_size": 0,
    }

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
logger = logging.getLogger("signalforge.database")


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables when AUTO_CREATE_SCHEMA is enabled."""
    if not settings.auto_create_schema:
        logger.info("Skipping Base.metadata.create_all (AUTO_CREATE_SCHEMA=false)")
        return

    # Ensure model modules are imported so SQLAlchemy metadata is populated.
    from backend.models import signal, incident, risk  # noqa: F401
    from backend.models import user, tenant, notification  # noqa: F401
    from backend.models import note  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """Dependency yielding an async DB session."""
    async with async_session() as session:
        yield session
