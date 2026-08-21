"""Add playback_events.detail for music_web client traces.

Revision ID: 109_playback_event_detail
Revises: 108_license_session_audit
"""

from alembic import op

revision = "109_playback_event_detail"
down_revision = "108_license_session_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE playback_events
          ADD COLUMN IF NOT EXISTS detail TEXT
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE playback_events DROP COLUMN IF EXISTS detail")
