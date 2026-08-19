"""Add WAV support for web music downloads.

Revision ID: 085_web_music_wav_support
Revises: 084_user_products_web_music
Create Date: 2026-08-16
"""

from __future__ import annotations

from alembic import op

revision = "085_web_music_wav_support"
down_revision = "084_user_products_web_music"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS wav_task_id_ok TEXT,
        ADD COLUMN IF NOT EXISTS wav_task_id_alt TEXT,
        ADD COLUMN IF NOT EXISTS wav_url_ok TEXT,
        ADD COLUMN IF NOT EXISTS wav_url_alt TEXT,
        ADD COLUMN IF NOT EXISTS wav_status_ok TEXT DEFAULT 'pending',
        ADD COLUMN IF NOT EXISTS wav_status_alt TEXT DEFAULT 'pending'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS wav_status_alt,
        DROP COLUMN IF EXISTS wav_status_ok,
        DROP COLUMN IF EXISTS wav_url_alt,
        DROP COLUMN IF EXISTS wav_url_ok,
        DROP COLUMN IF EXISTS wav_task_id_alt,
        DROP COLUMN IF EXISTS wav_task_id_ok
        """
    )
