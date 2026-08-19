"""User avatar URL and web music likes.

Revision ID: 099_user_avatar_web_music_likes
Revises: 098_web_music_suno_cover_urls
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "099_user_avatar_web_music_likes"
down_revision = "098_web_music_suno_cover_urls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_likes (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            task_id UUID NOT NULL REFERENCES suno_tasks(id) ON DELETE CASCADE,
            variant VARCHAR(8) NOT NULL DEFAULT 'ok',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, task_id, variant)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_likes_user_created
        ON web_music_likes (user_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_web_music_likes_user_created")
    op.execute("DROP TABLE IF EXISTS web_music_likes")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_url")
