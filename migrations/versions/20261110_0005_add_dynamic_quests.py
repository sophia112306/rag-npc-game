"""Add sourced dynamic quests.

Revision ID: 20261110_0005
Revises: 20261110_0004
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0005"
down_revision: str | None = "20261110_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quests",
        sa.Column("quest_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("giver_id", sa.String(length=100), nullable=False),
        sa.Column("recipient_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_turn", sa.Integer(), nullable=False),
        sa.Column("due_turn", sa.Integer(), nullable=True),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_quests_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("quest_id", name="pk_quests"),
    )
    op.create_index(
        "ix_quests_open",
        "quests",
        ["session_id", "recipient_id", "status", "created_turn"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_quests_open", table_name="quests")
    op.drop_table("quests")
