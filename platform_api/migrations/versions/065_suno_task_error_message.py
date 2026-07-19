"""Add error_message column to suno_tasks for provider failure detail."""

from __future__ import annotations

from alembic import op

revision = "065_suno_task_error_message"
down_revision = "064_daily_quota_bank"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS error_message TEXT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS error_message
        """
    )
