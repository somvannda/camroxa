"""Per-variant play counts for web music tracks.

Revision ID: 100_web_music_play_counts
Revises: 099_user_avatar_web_music_likes
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "100_web_music_play_counts"
down_revision = "099_user_avatar_web_music_likes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_play_counts (
            task_id UUID NOT NULL REFERENCES suno_tasks(id) ON DELETE CASCADE,
            variant VARCHAR(8) NOT NULL DEFAULT 'ok',
            play_count INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (task_id, variant)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_play_counts_count
        ON web_music_play_counts (play_count DESC, updated_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_web_music_play_counts_count")
    op.execute("DROP TABLE IF EXISTS web_music_play_counts")
