"""Persist Create-workspace stream-ready flags after origin audio is actually playable.

Revision ID: 106_web_music_stream_ready
Revises: 105_web_music_clip_titles
Create Date: 2026-08-18
"""

from __future__ import annotations

from alembic import op

revision = "106_web_music_stream_ready"
down_revision = "105_web_music_clip_titles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS stream_ready_ok BOOLEAN,
        ADD COLUMN IF NOT EXISTS stream_ready_alt BOOLEAN
        """
    )
    op.execute(
        """
        UPDATE suno_tasks
        SET stream_ready_ok = TRUE
        WHERE stream_ready_ok IS NULL
          AND (
            NULLIF(BTRIM(COALESCE(audio_url_ok, '')), '') IS NOT NULL
            OR NULLIF(BTRIM(COALESCE(b2_storage_key_ok, '')), '') IS NOT NULL
          )
        """
    )
    op.execute(
        """
        UPDATE suno_tasks
        SET stream_ready_alt = TRUE
        WHERE stream_ready_alt IS NULL
          AND (
            NULLIF(BTRIM(COALESCE(audio_url_alt, '')), '') IS NOT NULL
            OR NULLIF(BTRIM(COALESCE(b2_storage_key_alt, '')), '') IS NOT NULL
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS stream_ready_alt,
        DROP COLUMN IF EXISTS stream_ready_ok
        """
    )
