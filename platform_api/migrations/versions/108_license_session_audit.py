"""Add license session audit columns used by packaged play.

Revision ID: 108_license_session_audit
Revises: 107_protected_playback
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op

revision = "108_license_session_audit"
down_revision = "107_protected_playback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE content_license_sessions
        ADD COLUMN IF NOT EXISTS play_source TEXT,
        ADD COLUMN IF NOT EXISTS search_query TEXT,
        ADD COLUMN IF NOT EXISTS country TEXT,
        ADD COLUMN IF NOT EXISTS session_bind TEXT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE content_license_sessions
        DROP COLUMN IF EXISTS play_source,
        DROP COLUMN IF EXISTS search_query,
        DROP COLUMN IF EXISTS country,
        DROP COLUMN IF EXISTS session_bind
        """
    )
