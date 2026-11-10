"""Create persistent session and complete-turn tables.

Revision ID: 20261110_0001
Revises:
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_sessions",
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_id", name="pk_game_sessions"),
    )
    op.create_table(
        "action_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("action_id", sa.String(length=36), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_action_records_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_action_records"),
        sa.UniqueConstraint("session_id", "action_id", name="uq_action_records_session_action"),
    )
    op.create_index(
        "ix_action_records_session_created",
        "action_records",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "game_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("action_id", sa.String(length=36), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("cause_event_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("effect_json", sa.JSON(), nullable=False),
        sa.Column("visibility_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_game_events_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_game_events"),
    )
    op.create_index(
        "ix_game_events_session_turn",
        "game_events",
        ["session_id", "turn_number"],
        unique=False,
    )
    op.create_table(
        "dialogue_records",
        sa.Column("dialogue_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("action_id", sa.String(length=36), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("speaker_type", sa.String(length=20), nullable=False),
        sa.Column("speaker_id", sa.String(length=100), nullable=True),
        sa.Column("speaker_name", sa.String(length=100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("emotion", sa.String(length=50), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_dialogue_records_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dialogue_id", name="pk_dialogue_records"),
        sa.UniqueConstraint("session_id", "action_id", "position", name="uq_dialogue_turn_position"),
    )
    op.create_index(
        "ix_dialogue_records_session_turn",
        "dialogue_records",
        ["session_id", "turn_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dialogue_records_session_turn", table_name="dialogue_records")
    op.drop_table("dialogue_records")
    op.drop_index("ix_game_events_session_turn", table_name="game_events")
    op.drop_table("game_events")
    op.drop_index("ix_action_records_session_created", table_name="action_records")
    op.drop_table("action_records")
    op.drop_table("game_sessions")
