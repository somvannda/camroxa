"""Add Suno sanitize metadata on songs and channel-scoped blocklist terms."""

from __future__ import annotations

from alembic import op

revision = "067_song_suno_sanitize_metadata"
down_revision = "066_suno_blocklist_terms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE songs
        ADD COLUMN IF NOT EXISTS suno_last_sanitize JSONB,
        ADD COLUMN IF NOT EXISTS suno_auto_retry_count INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE suno_blocklist_terms
        ADD COLUMN IF NOT EXISTS channel_profile_id UUID
            REFERENCES channel_profiles(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_blocklist_terms_channel
        ON suno_blocklist_terms (channel_profile_id, enabled, severity)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_suno_blocklist_terms_channel")
    op.execute(
        """
        ALTER TABLE suno_blocklist_terms
        DROP COLUMN IF EXISTS channel_profile_id
        """
    )
    op.execute(
        """
        ALTER TABLE songs
        DROP COLUMN IF EXISTS suno_last_sanitize,
        DROP COLUMN IF EXISTS suno_auto_retry_count
        """
    )
