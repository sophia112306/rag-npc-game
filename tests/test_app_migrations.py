"""Application startup migration tests."""

import sqlite3

from fastapi.testclient import TestClient

from backend.main import create_app


def test_app_startup_applies_alembic_migration(tmp_path) -> None:
    database_path = tmp_path / "startup.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"

    with TestClient(create_app(database_url)) as client:
        assert client.get("/health").status_code == 200

    connection = sqlite3.connect(database_path)
    try:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert revision == ("20261110_0001",)
    assert {"game_sessions", "action_records", "game_events", "dialogue_records"} <= tables
