"""
app/database/session.py
-----------------------
Async SQLAlchemy engine, session factory, and FastAPI dependency.

The engine is created lazily on first access so that importing this module
(e.g. during testing) does not require ``asyncpg`` to be installed.
``asyncpg`` is only loaded when the engine actually tries to open a connection.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# ── Private lazy singletons ────────────────────────────────────────────────────
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None

# ── Synchronous session (used by ExperimentRunner + SafetyValidator) ───────────
# The Reliability Engine calls blocking Docker SDK methods, so async would add
# unnecessary complexity.  A separate synchronous engine/session is cleaner.
_sync_engine = None
_sync_session_factory: Optional[sessionmaker[Session]] = None


def _get_sync_engine():
    """Return the module-level synchronous engine, creating it on first call."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        # Convert asyncpg URL to psycopg2 (synchronous) URL
        sync_url = settings.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
    return _sync_engine


def _get_sync_session_factory() -> sessionmaker[Session]:
    """Return the module-level synchronous session factory."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=_get_sync_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _sync_session_factory


class SyncSessionLocal:
    """
    Context manager that provides a synchronous SQLAlchemy Session.

    Usage::

        with SyncSessionLocal() as db:
            db.query(...)
            db.commit()
    """

    def __enter__(self) -> Session:
        self._session = _get_sync_session_factory()()
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._session.rollback()
        self._session.close()


def _get_engine() -> AsyncEngine:
    """
    Return the module-level async engine, creating it on first call.

    Lazy initialisation means importing this module (e.g. in test discovery)
    does not immediately attempt to load the asyncpg dialect driver.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=(settings.APP_ENV == "development"),   # SQL echo only in dev
            pool_pre_ping=True,                         # validate on checkout
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level async session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session for a single request.

    The session is committed on success and rolled back on any exception,
    then closed in the ``finally`` block regardless of outcome.

    Usage
    -----
    ::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
