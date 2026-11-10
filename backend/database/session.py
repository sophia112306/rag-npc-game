"""Async database engine and session factory helpers."""

import os
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/game.db"


def get_database_url() -> str:
    """Read the application database URL without binding callers to SQLite."""

    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def ensure_sqlite_directory(database_url: str) -> None:
    """Create the parent directory for a file-backed SQLite database."""

    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def create_database_engine(database_url: str | None = None, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine for the configured database."""

    url = database_url or get_database_url()
    ensure_sqlite_directory(url)
    return create_async_engine(url, echo=echo)


def create_async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create sessions that keep ORM state available after commits."""

    return async_sessionmaker(engine, expire_on_commit=False)
