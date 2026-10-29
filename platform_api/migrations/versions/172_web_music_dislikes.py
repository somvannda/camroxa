"""Persist per-clip dislikes for web-music songs.

Mirrors `web_music_likes` so the thumbs-down control survives a reload and stays
mutually exclusive with a like on the same clip.

Revision ID: 172_web_music_dislikes
Revises: 171_purged_variants
"""

from __future__ import annotations

from alembic import op

revision: str = "172_web_music_dislikes"
down_revision: str | None = "171_purged_variants"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_dislikes (
            user_id UUID NOT NULL,
            task_id UUID NOT NULL REFERENCES suno_tasks(id) ON DELETE CASCADE,
            variant TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, task_id, variant)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_dislikes_task
            ON web_music_dislikes (task_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_web_music_dislikes_task")
    op.execute("DROP TABLE IF EXISTS web_music_dislikes")
