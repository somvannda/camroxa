"""Add a recoverable trash state to web-music generations.

Deleting a track used to hard-delete the row (and its files stayed behind until
the next sweep). It now moves to Trash first: `trashed_at` marks the row,
`restore` clears it, and a permanent delete removes the row.

Revision ID: 169_suno_task_trash
Revises: 168_reference_videos
"""

from __future__ import annotations

from alembic import op

revision: str = "169_suno_task_trash"
down_revision: str | None = "168_reference_videos"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS trashed_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_tasks_trashed
            ON suno_tasks (user_id, trashed_at)
            WHERE trashed_at IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_suno_tasks_trashed")
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS trashed_at")
