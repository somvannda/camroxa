"""Add pending profile add-on slots (paid but not yet onboarded)."""

from alembic import op

revision = "052_profile_addon_pending"
down_revision = "051_daily_image_per_channel_standard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE licenses
        ADD COLUMN IF NOT EXISTS profile_addon_pending INTEGER NOT NULL DEFAULT 0
            CHECK (profile_addon_pending >= 0 AND profile_addon_pending <= 8)
        """
    )
    # Tighten active add-on cap to match 10-channel account maximum (8 add-on slots on 2-channel base).
    op.execute(
        """
        ALTER TABLE licenses DROP CONSTRAINT IF EXISTS licenses_profile_addon_slots_check
        """
    )
    op.execute(
        """
        ALTER TABLE licenses
        ADD CONSTRAINT licenses_profile_addon_slots_check
            CHECK (profile_addon_slots >= 0 AND profile_addon_slots <= 8)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE licenses DROP COLUMN IF EXISTS profile_addon_pending")
    op.execute(
        """
        ALTER TABLE licenses DROP CONSTRAINT IF EXISTS licenses_profile_addon_slots_check
        """
    )
    op.execute(
        """
        ALTER TABLE licenses
        ADD CONSTRAINT licenses_profile_addon_slots_check
            CHECK (profile_addon_slots >= 0 AND profile_addon_slots <= 18)
        """
    )
