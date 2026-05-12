"""Sync SQLAlchemy session for V2 background processes.

V2 runs on Windows as a long-lived process; uses sync engine against the
shared Postgres (already running on Linux).
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .config import get_v2_settings


@lru_cache()
def _engine():
    settings = get_v2_settings()
    return create_engine(
        settings.DATABASE_URL_SYNC,
        pool_size=10,
        max_overflow=10,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache()
def _session_factory():
    return sessionmaker(bind=_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Session:
    """Provide a transactional scope around a series of operations."""
    SessionLocal = _session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
