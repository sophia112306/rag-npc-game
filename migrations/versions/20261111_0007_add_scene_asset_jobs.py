"""Add durable Hunyuan scene asset jobs.

Revision ID: 20261111_0007
Revises: 20261110_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20261111_0007"
down_revision = "20261110_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scene_asset_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(100), sa.ForeignKey("game_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("model_url", sa.String(500)),
        sa.Column("fallback_url", sa.String(500), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "fingerprint", name="uq_scene_asset_jobs_session_fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("scene_asset_jobs")
