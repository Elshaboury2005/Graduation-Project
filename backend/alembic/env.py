"""
alembic/env.py
--------------
Alembic migration environment.

Configured for *async* SQLAlchemy via asyncpg.  The DATABASE_URL is read
from the application's Settings object (never hard-coded).  All ORM models
are imported so auto-generate can detect schema changes automatically.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# ── Load application settings ──────────────────────────────────────────────────
from app.core.config import get_settings

# ── Import *every* model so Alembic can auto-detect tables ────────────────────
import app.models  # noqa: F401  — registers all models with Base.metadata
from app.database.base import Base

# ── Alembic Config object ──────────────────────────────────────────────────────
config = context.config

# Set up Python logging from alembic.ini [loggers] section (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic which metadata to compare against for auto-generate
target_metadata = Base.metadata


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_url() -> str:
    """Return the database URL from application settings."""
    return get_settings().DATABASE_URL


# ── Offline migrations (generate SQL without a live DB) ───────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This emits SQL to stdout / a file without connecting to the database.
    Useful for generating migration scripts to review before applying.
    """
    url = get_url()
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


# ── Online migrations (apply against a live DB) ───────────────────────────────

def do_run_migrations(connection) -> None:
    """Configure and run migrations using *connection*."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using an async engine.

    asyncpg does not support the synchronous connection interface that
    Alembic uses internally, so we run the sync migration function inside
    ``run_sync`` on an async connection.
    """
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,  # don't keep connections open after migration
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# ── Entry point ────────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
