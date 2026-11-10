"""Migration-level tests for the M2a persistence schema."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


EXPECTED_TABLES = {
    "action_records",
    "alembic_version",
    "dialogue_records",
    "game_events",
    "game_sessions",
}


def test_initial_migration_creates_complete_turn_schema(tmp_path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    assert {column["name"] for column in inspector.get_columns("game_sessions")} >= {
        "session_id",
        "state_version",
        "turn_count",
        "state_json",
    }
    unique_constraints = inspector.get_unique_constraints("action_records")
    assert {tuple(item["column_names"]) for item in unique_constraints} == {
        ("session_id", "action_id")
    }
    engine.dispose()


def test_initial_migration_can_be_reverted(tmp_path) -> None:
    database_path = tmp_path / "downgrade.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(f"sqlite:///{database_path}")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
