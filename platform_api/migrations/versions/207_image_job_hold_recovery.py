"""Track image-job billing holds and provider invocation for stale recovery.

Revision ID: 207
Revises: 206
Create Date: 2026-11-17

A crashed image worker can leave a job in ``running`` after the wallet hold was
taken. The existing job_queue sweeper only recovers the queue row, not the image
job. These columns let the image sweeper refund the exact hold and decide
whether platform COGS was actually incurred.
"""

from __future__ import annotations

from alembic import op

revision = "207"
down_revision = "206"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE image_jobs
            ADD COLUMN IF NOT EXISTS hold_units BIGINT NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS hold_state TEXT NOT NULL DEFAULT 'none',
            ADD COLUMN IF NOT EXISTS provider_invoked BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_jobs_status_updated
        ON image_jobs(status, updated_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_jobs_hold_state
        ON image_jobs(hold_state)
        WHERE hold_state = 'held'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_image_jobs_hold_state")
    op.execute("DROP INDEX IF EXISTS idx_image_jobs_status_updated")
    op.execute(
        """
        ALTER TABLE image_jobs
            DROP COLUMN IF EXISTS provider_invoked,
            DROP COLUMN IF EXISTS hold_state,
            DROP COLUMN IF EXISTS hold_units
        """
    )
