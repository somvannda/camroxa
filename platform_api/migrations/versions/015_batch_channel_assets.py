"""Create batch_channel_assets manifest table."""

from __future__ import annotations

from alembic import op

revision = "015_batch_channel_assets"
down_revision = "014_create_image_sample_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_channel_assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            profile_id UUID NOT NULL REFERENCES channel_profiles(id) ON DELETE CASCADE,
            role VARCHAR(10) NOT NULL,
            run_dir TEXT,
            source_mode TEXT NOT NULL DEFAULT 'manual',
            background_16x9_path TEXT,
            background_9x16_path TEXT,
            thumbnail_16x9_path TEXT,
            thumbnail_9x16_path TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_batch_channel_assets_triplet
            ON batch_channel_assets(batch_id, profile_id, role)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_batch_channel_assets_user_batch
            ON batch_channel_assets(user_id, batch_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_batch_channel_assets_user_batch")
    op.execute("DROP INDEX IF EXISTS uq_batch_channel_assets_triplet")
    op.execute("DROP TABLE IF EXISTS batch_channel_assets")
