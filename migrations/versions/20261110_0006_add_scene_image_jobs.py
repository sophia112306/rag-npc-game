"""Add persistent post-commit scene image jobs.

Revision ID: 20261110_0006
Revises: 20261110_0005
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0006"
down_revision: str | None = "20261110_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scene_image_jobs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("scene_id", sa.String(length=100), nullable=False),
        sa.Column("story_node_id", sa.String(length=100), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("prompt_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("fallback_url", sa.String(length=500), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.session_id"],
            name="fk_scene_image_jobs_session_id_game_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_id", name="pk_scene_image_jobs"),
        sa.UniqueConstraint(
            "session_id",
            "prompt_fingerprint",
            name="uq_scene_image_jobs_session_fingerprint",
        ),
    )
    op.create_index(
        "ix_scene_image_jobs_session_created",
        "scene_image_jobs",
        ["session_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scene_image_jobs_session_created", table_name="scene_image_jobs")
    op.drop_table("scene_image_jobs")
