"""Seed 6-month and annual plan rows for each channel tier."""

from alembic import op

revision = "050_channel_plan_billing_terms"
down_revision = "049_profile_addons_and_channel_tiers"
branch_labels = None
depends_on = None

# (channels, monthly_name_suffix, monthly_cents, song, draft, image, video, merge, daily_video, daily_merge)
_TIERS = (
    (2, "2-channel", 7900, 300, 1260, 120, 300, 30, 10, 1),
    (6, "6-channel", 19039, 900, 3780, 360, 900, 90, 30, 3),
    (10, "10-channel", 28124, 1500, 6300, 600, 1500, 150, 50, 5),
)


def _insert_term(
    *,
    name: str,
    price_cents: int,
    billing_cycle_days: int,
    channels: int,
    song: int,
    draft: int,
    image: int,
    video: int,
    merge: int,
    daily_video: int,
    daily_merge: int,
) -> str:
    return f"""
        INSERT INTO plans (
            name, price_cents, billing_cycle_days, profile_allowance,
            monthly_song_limit, monthly_draft_limit, monthly_image_limit,
            monthly_video_limit, monthly_merge_limit,
            daily_song_limit_per_channel, daily_draft_limit_per_channel,
            daily_image_limit_per_channel, daily_video_limit, daily_merge_limit,
            is_active, effective_from, created_at, updated_at
        )
        SELECT
            '{name}',
            {price_cents},
            {billing_cycle_days},
            {channels},
            {song},
            {draft},
            {image},
            {video},
            {merge},
            10,
            21,
            2,
            {daily_video},
            {daily_merge},
            true,
            NOW(),
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM plans
            WHERE LOWER(name) = LOWER('{name}')
        )
    """


def upgrade() -> None:
    for channels, suffix, monthly_cents, song, draft, image, video, merge, daily_video, daily_merge in _TIERS:
        semi_total = int(round(monthly_cents * 6 * 0.85))
        annual_total = int(round(monthly_cents * 12 * 0.75))

        op.execute(
            _insert_term(
                name=f"6 Months · {suffix}",
                price_cents=semi_total,
                billing_cycle_days=180,
                channels=channels,
                song=song,
                draft=draft,
                image=image,
                video=video,
                merge=merge,
                daily_video=daily_video,
                daily_merge=daily_merge,
            )
        )
        op.execute(
            _insert_term(
                name=f"Annual · {suffix}",
                price_cents=annual_total,
                billing_cycle_days=365,
                channels=channels,
                song=song,
                draft=draft,
                image=image,
                video=video,
                merge=merge,
                daily_video=daily_video,
                daily_merge=daily_merge,
            )
        )

    # Normalize monthly plan names to the channel-first convention.
    op.execute(
        """
        UPDATE plans SET name = 'Monthly · 2-channel', updated_at = NOW()
        WHERE LOWER(name) IN ('monthly 2-channel', 'monthly · 2-channel')
        """
    )
    op.execute(
        """
        UPDATE plans SET name = 'Monthly · 6-channel', updated_at = NOW()
        WHERE LOWER(name) IN ('monthly 6-channel', 'monthly · 6-channel')
        """
    )
    op.execute(
        """
        UPDATE plans SET name = 'Monthly · 10-channel', updated_at = NOW()
        WHERE LOWER(name) IN ('monthly 10-channel', 'monthly · 10-channel')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM plans
        WHERE LOWER(name) LIKE '6 months · %'
           OR LOWER(name) LIKE 'annual · %'
        """
    )
