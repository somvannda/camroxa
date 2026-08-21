"""Add HLS packaging fields for iOS Safari playback.

Revision ID: 108_add_hls_packaging
Revises: 107_protected_playback
Create Date: 2026-08-21
"""

from __future__ import annotations

from alembic import op

revision = "108_add_hls_packaging"
down_revision = "107_protected_playback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE stream_tracks
        ADD COLUMN IF NOT EXISTS hls_prefix VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS hls_status VARCHAR(20) NOT NULL DEFAULT 'none'
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS hls_prefix_ok VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS hls_prefix_alt VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS hls_status_ok VARCHAR(20) NOT NULL DEFAULT 'none',
        ADD COLUMN IF NOT EXISTS hls_status_alt VARCHAR(20) NOT NULL DEFAULT 'none'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_tasks_hls_status_ok
        ON suno_tasks (hls_status_ok)
        WHERE hls_status_ok = 'ready'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_tasks_hls_status_alt
        ON suno_tasks (hls_status_alt)
        WHERE hls_status_alt = 'ready'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_suno_tasks_hls_status_alt")
    op.execute("DROP INDEX IF EXISTS idx_suno_tasks_hls_status_ok")
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS hls_status_alt,
        DROP COLUMN IF EXISTS hls_status_ok,
        DROP COLUMN IF EXISTS hls_prefix_alt,
        DROP COLUMN IF EXISTS hls_prefix_ok
        """
    )
    op.execute(
        """
        ALTER TABLE stream_tracks
        DROP COLUMN IF EXISTS hls_status,
        DROP COLUMN IF EXISTS hls_prefix
        """
    )
