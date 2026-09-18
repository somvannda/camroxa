"""Durable B2 backfill: permanent-failure + last-attempt tracking on upload jobs.

Revision ID: 121_upload_job_permanent_failed
Revises: 120_suno_download_unavailable
Create Date: 2026-09-18
"""

from __future__ import annotations

from alembic import op

revision = "121_upload_job_permanent_failed"
down_revision = "120_suno_download_unavailable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE stream_upload_jobs
        ADD COLUMN IF NOT EXISTS permanent_failed BOOLEAN NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stream_upload_jobs_backfill
        ON stream_upload_jobs (status, permanent_failed, created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_stream_upload_jobs_backfill")
    op.execute(
        """
        ALTER TABLE stream_upload_jobs
        DROP COLUMN IF EXISTS permanent_failed,
        DROP COLUMN IF EXISTS last_attempt_at
        """
    )
