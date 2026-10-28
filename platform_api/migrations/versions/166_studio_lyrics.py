"""Add saved lyric drafts.

Revision ID: 166_studio_lyrics
Revises: 165_suno_task_persona
"""

from __future__ import annotations

from alembic import op

revision: str = "166_studio_lyrics"
down_revision: str | None = "165_suno_task_persona"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_lyrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_lyrics_user_updated_idx
            ON studio_lyrics (user_id, updated_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS studio_lyrics_user_updated_idx")
    op.execute("DROP TABLE IF EXISTS studio_lyrics")
