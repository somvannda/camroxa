"""Add Suno cover image URLs to suno_tasks for web music track art.

Revision ID: 098_web_music_suno_cover_urls
Revises: 097_web_subscriptions_pending_status
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "098_web_music_suno_cover_urls"
down_revision = "097_web_subscriptions_pending_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS image_url_ok VARCHAR(1000),
        ADD COLUMN IF NOT EXISTS image_url_alt VARCHAR(1000)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS image_url_alt,
        DROP COLUMN IF EXISTS image_url_ok
        """
    )
