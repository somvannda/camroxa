"""Add Backblaze storage tracking for web music

Revision ID: 087_web_music_b2_storage
Revises: 086_suno_advanced_settings
Create Date: 2026-08-16 13:45:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "087_web_music_b2_storage"
down_revision = "086_suno_advanced_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Backblaze B2 storage keys and upload timestamps to suno_tasks."""
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS b2_storage_key_ok TEXT,
        ADD COLUMN IF NOT EXISTS b2_storage_key_alt TEXT,
        ADD COLUMN IF NOT EXISTS b2_uploaded_at_ok TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS b2_uploaded_at_alt TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS b2_wav_storage_key_ok TEXT,
        ADD COLUMN IF NOT EXISTS b2_wav_storage_key_alt TEXT,
        ADD COLUMN IF NOT EXISTS b2_wav_uploaded_at_ok TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS b2_wav_uploaded_at_alt TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    """Remove Backblaze storage columns from suno_tasks."""
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS b2_storage_key_ok,
        DROP COLUMN IF EXISTS b2_storage_key_alt,
        DROP COLUMN IF EXISTS b2_uploaded_at_ok,
        DROP COLUMN IF EXISTS b2_uploaded_at_alt,
        DROP COLUMN IF EXISTS b2_wav_storage_key_ok,
        DROP COLUMN IF EXISTS b2_wav_storage_key_alt,
        DROP COLUMN IF EXISTS b2_wav_uploaded_at_ok,
        DROP COLUMN IF EXISTS b2_wav_uploaded_at_alt
        """
    )
