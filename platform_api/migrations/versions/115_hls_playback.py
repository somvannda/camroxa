"""HLS storage columns for iOS Safari AES-128 playback.

Revision ID: 115_hls_playback
Revises: 109_playback_event_detail
Create Date: 2026-08-21
"""

from __future__ import annotations

from alembic import op

revision = "115_hls_playback"
down_revision = "109_playback_event_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE stream_tracks
        ADD COLUMN IF NOT EXISTS hls_storage_prefix TEXT,
        ADD COLUMN IF NOT EXISTS hls_status TEXT NOT NULL DEFAULT 'none'
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS hls_storage_prefix_ok TEXT,
        ADD COLUMN IF NOT EXISTS hls_storage_prefix_alt TEXT,
        ADD COLUMN IF NOT EXISTS hls_status_ok TEXT NOT NULL DEFAULT 'none',
        ADD COLUMN IF NOT EXISTS hls_status_alt TEXT NOT NULL DEFAULT 'none'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE stream_tracks
        DROP COLUMN IF EXISTS hls_storage_prefix,
        DROP COLUMN IF EXISTS hls_status
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS hls_storage_prefix_ok,
        DROP COLUMN IF EXISTS hls_storage_prefix_alt,
        DROP COLUMN IF EXISTS hls_status_ok,
        DROP COLUMN IF EXISTS hls_status_alt
        """
    )
