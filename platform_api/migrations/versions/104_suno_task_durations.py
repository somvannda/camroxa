"""Store Suno clip durations on suno_tasks for web music display.

Revision ID: 104_suno_task_durations
Revises: 103_merge_credit_refund_heads
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "104_suno_task_durations"
down_revision = "103_merge_credit_refund_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS duration_ok DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS duration_alt DOUBLE PRECISION
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS duration_alt,
        DROP COLUMN IF EXISTS duration_ok
        """
    )
