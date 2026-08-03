"""Durable platform job queue for work moved off uvicorn HTTP workers.

Revision ID: 080_job_queue
Revises: 079_image_job_storage_key
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "080_job_queue"
down_revision = "079_image_job_storage_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_queue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("song_id", UUID(as_uuid=True), sa.ForeignKey("songs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "idx_job_queue_claimable",
        "job_queue",
        ["status", "run_after", "priority", "created_at"],
        postgresql_where=sa.text("status IN ('queued', 'delayed')"),
    )
    op.create_index("idx_job_queue_user", "job_queue", ["user_id", "status"])
    op.create_index("idx_job_queue_batch", "job_queue", ["batch_id"])


def downgrade() -> None:
    op.drop_index("idx_job_queue_batch", table_name="job_queue")
    op.drop_index("idx_job_queue_user", table_name="job_queue")
    op.drop_index("idx_job_queue_claimable", table_name="job_queue")
    op.drop_table("job_queue")
