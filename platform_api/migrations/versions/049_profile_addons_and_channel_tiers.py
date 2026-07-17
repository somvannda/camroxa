"""Add profile add-on slots and seed 6 / 10 channel monthly tier plans."""

from alembic import op

revision = "049_profile_addons_and_channel_tiers"
down_revision = "048_plan_video_merge_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE licenses
        ADD COLUMN IF NOT EXISTS profile_addon_slots INTEGER NOT NULL DEFAULT 0
            CHECK (profile_addon_slots >= 0 AND profile_addon_slots <= 18)
        """
    )

    # Rename legacy single-tier monthly plan for clarity when present.
    op.execute(
        """
        UPDATE plans
        SET name = 'Monthly · 2-channel',
            updated_at = NOW()
        WHERE LOWER(name) = 'monthly'
        """
    )

    # 6-channel tier (3× account-wide monthly meters vs 2-channel standard).
    op.execute(
        """
        INSERT INTO plans (
            name, price_cents, billing_cycle_days, profile_allowance,
            monthly_song_limit, monthly_draft_limit, monthly_image_limit,
            monthly_video_limit, monthly_merge_limit,
            daily_song_limit_per_channel, daily_draft_limit_per_channel,
            daily_image_limit_per_channel, daily_video_limit, daily_merge_limit,
            is_active, effective_from, created_at, updated_at
        )
        SELECT
            'Monthly · 6-channel',
            19039,
            30,
            6,
            900,
            3780,
            360,
            900,
            90,
            10,
            21,
            2,
            30,
            3,
            true,
            NOW(),
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM plans WHERE LOWER(name) = 'monthly · 6-channel'
        )
        """
    )

    # 10-channel tier (5× account-wide monthly meters vs 2-channel standard).
    op.execute(
        """
        INSERT INTO plans (
            name, price_cents, billing_cycle_days, profile_allowance,
            monthly_song_limit, monthly_draft_limit, monthly_image_limit,
            monthly_video_limit, monthly_merge_limit,
            daily_song_limit_per_channel, daily_draft_limit_per_channel,
            daily_image_limit_per_channel, daily_video_limit, daily_merge_limit,
            is_active, effective_from, created_at, updated_at
        )
        SELECT
            'Monthly · 10-channel',
            28124,
            30,
            10,
            1500,
            6300,
            600,
            1500,
            150,
            10,
            21,
            2,
            50,
            5,
            true,
            NOW(),
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM plans WHERE LOWER(name) = 'monthly · 10-channel'
        )
        """
    )

    # Ensure the 2-channel base row carries the documented standard price when unset.
    op.execute(
        """
        UPDATE plans
        SET price_cents = 7900,
            profile_allowance = 2,
            monthly_song_limit = 300,
            monthly_draft_limit = 1260,
            monthly_image_limit = 120,
            monthly_video_limit = 300,
            monthly_merge_limit = 30,
            daily_song_limit_per_channel = 10,
            daily_draft_limit_per_channel = 21,
            daily_image_limit_per_channel = 2,
            daily_video_limit = 10,
            daily_merge_limit = 1,
            billing_cycle_days = 30,
            updated_at = NOW()
        WHERE LOWER(name) IN ('monthly 2-channel', 'monthly · 2-channel')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET name = 'monthly',
            updated_at = NOW()
        WHERE LOWER(name) IN ('monthly 2-channel', 'monthly · 2-channel')
        """
    )
    op.execute("DELETE FROM plans WHERE LOWER(name) IN ('monthly · 6-channel', 'monthly · 10-channel', 'monthly 6-channel', 'monthly 10-channel')")
    op.execute("ALTER TABLE licenses DROP COLUMN IF EXISTS profile_addon_slots")
