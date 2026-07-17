"""Add plan_kind and seed profile add-on plan rows."""

from alembic import op

revision = "054_plan_kind_profile_addons"
down_revision = "053_channel_pricing_config"
branch_labels = None
depends_on = None

ADDON_SEEDS = (
    (2, 7900, "Add-on · +2 channels"),
    (4, 15800, "Add-on · +4 channels"),
    (6, 23700, "Add-on · +6 channels"),
    (8, 31600, "Add-on · +8 channels"),
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS plan_kind VARCHAR(32) NOT NULL DEFAULT 'subscription'
            CHECK (plan_kind IN ('subscription', 'profile_addon'))
        """
    )

    for channels, cents, name in ADDON_SEEDS:
        op.execute(
            f"""
            INSERT INTO plans (
                name, price_cents, billing_cycle_days, profile_allowance,
                monthly_song_limit, monthly_image_limit, monthly_draft_limit,
                monthly_video_limit, monthly_merge_limit,
                daily_song_limit_per_channel, daily_image_limit_per_channel,
                daily_draft_limit_per_channel, daily_video_limit, daily_merge_limit,
                plan_kind, is_active, effective_from, created_at, updated_at
            )
            SELECT
                '{name}', {cents}, 30, {channels},
                0, 0, 0, 0, 0,
                1, 1, 1, 1, 1,
                'profile_addon', true, NOW(), NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM plans
                WHERE plan_kind = 'profile_addon'
                  AND profile_allowance = {channels}
                  AND billing_cycle_days = 30
            )
            """
        )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE plan_kind = 'profile_addon'")
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS plan_kind")
