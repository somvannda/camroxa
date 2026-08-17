"""Add Backblaze LRC storage keys for web music timed lyrics.

Revision ID: 101_web_music_b2_lrc_storage
Revises: 100_web_music_play_counts
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "101_web_music_b2_lrc_storage"
down_revision = "100_web_music_play_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS b2_lrc_storage_key_ok TEXT,
        ADD COLUMN IF NOT EXISTS b2_lrc_storage_key_alt TEXT,
        ADD COLUMN IF NOT EXISTS b2_lrc_uploaded_at_ok TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS b2_lrc_uploaded_at_alt TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS b2_lrc_storage_key_ok,
        DROP COLUMN IF EXISTS b2_lrc_storage_key_alt,
        DROP COLUMN IF EXISTS b2_lrc_uploaded_at_ok,
        DROP COLUMN IF EXISTS b2_lrc_uploaded_at_alt
        """
    )
