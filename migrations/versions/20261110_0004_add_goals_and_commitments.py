"""Add sourced NPC goals and commitments.

Revision ID: 20261110_0004
Revises: 20261110_0003
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0004"
down_revision: str | None = "20261110_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "npc_goals",
        sa.Column("goal_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("npc_id", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_turn", sa.Integer(), nullable=False),
        sa.Column("next_review_turn", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_npc_goals_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("goal_id", name="pk_npc_goals"),
    )
    op.create_index(
        "ix_npc_goals_due",
        "npc_goals",
        ["session_id", "npc_id", "status", "next_review_turn"],
        unique=False,
    )
    op.create_table(
        "commitments",
        sa.Column("commitment_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("promisor_id", sa.String(length=100), nullable=False),
        sa.Column("promisee_id", sa.String(length=100), nullable=False),
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
            name="fk_commitments_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("commitment_id", name="pk_commitments"),
    )
    op.create_index(
        "ix_commitments_active",
        "commitments",
        ["session_id", "status", "created_turn"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_commitments_active", table_name="commitments")
    op.drop_table("commitments")
    op.drop_index("ix_npc_goals_due", table_name="npc_goals")
    op.drop_table("npc_goals")
