"""Per-clip titles for web music Version 1 / Version 2.

Revision ID: 105_web_music_clip_titles
Revises: 104_suno_task_durations
Create Date: 2026-08-18
"""

from __future__ import annotations

from alembic import op

revision = "105_web_music_clip_titles"
down_revision = "104_suno_task_durations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS title_ok TEXT,
        ADD COLUMN IF NOT EXISTS title_alt TEXT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS title_alt,
        DROP COLUMN IF EXISTS title_ok
        """
    )
