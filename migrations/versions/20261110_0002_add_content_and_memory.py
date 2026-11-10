"""Add canon, character definition, knowledge, and memory tables.

Revision ID: 20261110_0002
Revises: 20261110_0001
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0002"
down_revision: str | None = "20261110_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "world_canon",
        sa.Column("canon_id", sa.String(length=100), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=200), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=True),
        sa.Column("certainty", sa.String(length=30), nullable=False),
        sa.Column("disclosure_scope", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("setting_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("canon_id", name="pk_world_canon"),
    )
    op.create_index(
        "ix_world_canon_disclosure_status",
        "world_canon",
        ["disclosure_scope", "status"],
        unique=False,
    )
    op.create_table(
        "character_definitions",
        sa.Column("npc_id", sa.String(length=100), nullable=False),
        sa.Column("public_profile_json", sa.JSON(), nullable=False),
        sa.Column("private_profile_json", sa.JSON(), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("setting_version", sa.Integer(), nullable=False),
        sa.Column("completeness_status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("npc_id", name="pk_character_definitions"),
    )
    op.create_table(
        "knowledge_records",
        sa.Column("knowledge_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("knower_npc_id", sa.String(length=100), nullable=False),
        sa.Column("subject_key", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("epistemic_status", sa.String(length=30), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("acquired_turn", sa.Integer(), nullable=False),
        sa.Column("available_from_turn", sa.Integer(), nullable=False),
        sa.Column("is_unlocked", sa.Boolean(), nullable=False),
        sa.Column("disclosure_scope", sa.String(length=30), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_knowledge_records_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("knowledge_id", name="pk_knowledge_records"),
    )
    op.create_index(
        "ix_knowledge_records_authorized_context",
        "knowledge_records",
        ["session_id", "knower_npc_id", "is_unlocked", "available_from_turn"],
        unique=False,
    )
    op.create_table(
        "memory_records",
        sa.Column("memory_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("npc_id", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(length=30), nullable=False),
        sa.Column("source_event_id", sa.String(length=36), nullable=True),
        sa.Column("source_action_id", sa.String(length=36), nullable=True),
        sa.Column("occurred_turn", sa.Integer(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_memory_records_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("memory_id", name="pk_memory_records"),
    )
    op.create_index(
        "ix_memory_records_npc_turn",
        "memory_records",
        ["session_id", "npc_id", "occurred_turn"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_memory_records_npc_turn", table_name="memory_records")
    op.drop_table("memory_records")
    op.drop_index("ix_knowledge_records_authorized_context", table_name="knowledge_records")
    op.drop_table("knowledge_records")
    op.drop_table("character_definitions")
    op.drop_index("ix_world_canon_disclosure_status", table_name="world_canon")
    op.drop_table("world_canon")
