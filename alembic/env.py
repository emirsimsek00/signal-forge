from __future__ import annotations

from logging.config import fileConfig
from uuid import uuid4

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.config import settings
from backend.database import Base

# Import models so metadata is fully populated for autogenerate.
from backend.models import incident, note, notification, risk, signal, tenant, user  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _migration_database_url() -> str:
    # Always prefer app settings so Alembic tracks the same target DB as FastAPI.
    configured = (settings.database_url or "").strip()
    if configured:
        return configured

    fallback = config.get_main_option("sqlalchemy.url", "").strip()
    if fallback:
        return fallback

    raise RuntimeError("DATABASE_URL is not configured for Alembic migrations.")


def run_migrations_offline() -> None:
    url = _migration_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    migration_url = _migration_database_url()
    configuration["sqlalchemy.url"] = migration_url

    connect_args = {}
    # Supabase pooler/PgBouncer can raise DuplicatePreparedStatementError
    # with asyncpg's default numeric statement names.
    if migration_url.startswith("postgresql+asyncpg://"):
        connect_args["prepared_statement_name_func"] = lambda: f"__alembic_{uuid4()}__"

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(_run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
