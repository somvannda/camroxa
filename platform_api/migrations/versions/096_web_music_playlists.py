"""Add web music playlists and playlist items.

Revision ID: 096_web_music_playlists
Revises: 095_web_music_daily_credits
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "096_web_music_playlists"
down_revision = "095_web_music_daily_credits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_playlists (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            slug VARCHAR(250) NOT NULL,
            description TEXT,
            is_public BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, slug)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_playlists_user_id
        ON web_music_playlists (user_id, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_playlists_public
        ON web_music_playlists (is_public, updated_at DESC)
        WHERE is_public = true
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_playlist_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            playlist_id UUID NOT NULL REFERENCES web_music_playlists(id) ON DELETE CASCADE,
            suno_task_id UUID NOT NULL REFERENCES suno_tasks(id) ON DELETE CASCADE,
            variant VARCHAR(8) NOT NULL DEFAULT 'ok',
            position INTEGER NOT NULL,
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(playlist_id, suno_task_id, variant)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_playlist_items_playlist
        ON web_music_playlist_items (playlist_id, position ASC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS web_music_playlist_items")
    op.execute("DROP TABLE IF EXISTS web_music_playlists")
