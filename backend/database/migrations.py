"""Programmatic Alembic migration runner for application startup."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from .session import ensure_sqlite_directory, get_database_url


def _upgrade_database(database_url: str) -> None:
    ensure_sqlite_directory(database_url)
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(config_path))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


async def upgrade_database(database_url: str | None = None) -> None:
    """Upgrade the configured database without blocking the event loop."""

    await asyncio.to_thread(_upgrade_database, database_url or get_database_url())
