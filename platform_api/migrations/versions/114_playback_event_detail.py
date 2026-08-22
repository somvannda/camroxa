"""Add playback_events.detail for music_web client traces."""

from alembic import op

revision = "114_playback_event_detail"
down_revision = "113_artist_page_tracks"
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
