"""Reprice web music plans to the $5/$10/$20/$30 ladder and refresh top-up packs.

music.camxora.com now follows the same credit value as musicapi.camxora.com
(350 credits per USD at the entry tier), so the paid monthly tiers become:

    Starter  $5  -> 1,750 credits/mo
    Creator  $10 -> 3,500 credits/mo
    Pro      $20 -> 7,000 credits/mo
    Studio   $30 -> 10,500 credits/mo

Yearly rows keep the existing 15% discount. The Free plan is intentionally left
untouched (it is admin-managed and already grants the 50-credit testing allowance).

Top-up packs become three recommended tiers with a volume bonus on top of the
350 cr/$ base:

    $5  -> 2,275 credits (+30%)
    $10 -> 4,200 credits (+20%)
    $30 -> 11,550 credits (+10%)

Revision ID: 127_web_music_plans_v2
Revises: 126_provider_base_url
Create Date: 2026-10-04
"""

from __future__ import annotations

from alembic import op

revision = "127_web_music_plans_v2"
down_revision = "126_provider_base_url"
branch_labels = None
depends_on = None

_PAID_FEATURES = (
    "ARRAY['Web Create', 'Desktop studio', 'Dual channels', 'Top-up packs']::text[]"
)
_FEATURES_JSON = '\'{"music": true, "images": true, "topup": true}\'::jsonb'

# (name, price_cents, billing_cycle_days, monthly_credits, display_order)
_PLANS = (
    ("starter_monthly", 500, 30, 1750, 1),
    ("starter_yearly", 5100, 365, 1750, 1),
    ("creator_monthly", 1000, 30, 3500, 2),
    ("creator_yearly", 10200, 365, 3500, 2),
    ("pro_monthly", 2000, 30, 7000, 3),
    ("pro_yearly", 20400, 365, 7000, 3),
    ("studio_monthly", 3000, 30, 10500, 4),
    ("studio_yearly", 30600, 365, 10500, 4),
)

# (slug, name, total_credits, price_cents, display_order)
_PACKS = (
    ("small", "Small Pack", 2275, 500, 1),
    ("medium", "Medium Pack", 4200, 1000, 2),
    ("large", "Large Pack", 11550, 3000, 3),
)


def upgrade() -> None:
    plan_values = ",\n            ".join(
        "('{name}', 'web_music', {price}, {days}, {credits}, 1, NULL, 999, "
        "{features}, true, {order}, true, {paid_features}, '{{}}'::text[])".format(
            name=name,
            price=price,
            days=days,
            credits=credits,
            features=_FEATURES_JSON,
            order=order,
            paid_features=_PAID_FEATURES,
        )
        for name, price, days, credits, order in _PLANS
    )
    op.execute(
        f"""
        INSERT INTO plans (
            name, plan_type, price_cents, billing_cycle_days, monthly_credits,
            profile_allowance, monthly_song_limit, daily_song_limit_per_channel,
            features, is_public, display_order, is_active,
            pricing_features, pricing_credit_lines
        ) VALUES
            {plan_values}
        ON CONFLICT (name) DO UPDATE SET
            plan_type = 'web_music',
            price_cents = EXCLUDED.price_cents,
            billing_cycle_days = EXCLUDED.billing_cycle_days,
            monthly_credits = EXCLUDED.monthly_credits,
            profile_allowance = EXCLUDED.profile_allowance,
            daily_song_limit_per_channel = EXCLUDED.daily_song_limit_per_channel,
            features = EXCLUDED.features,
            is_public = true,
            display_order = EXCLUDED.display_order,
            is_active = true,
            pricing_features = EXCLUDED.pricing_features,
            pricing_credit_lines = EXCLUDED.pricing_credit_lines,
            updated_at = NOW()
        """
    )

    pack_values = ",\n            ".join(
        "('{slug}', '{name}', 'web_music', {credits}, {price}, {songs}, {requests}, "
        "{order}, true)".format(
            slug=slug,
            name=name,
            credits=credits,
            price=price,
            songs=credits // 10,
            requests=credits // 10,
            order=order,
        )
        for slug, name, credits, price, order in _PACKS
    )
    op.execute(
        f"""
        INSERT INTO credit_packs (
            slug, name, pack_type, total_credits, price_cents,
            song_credits, request_count, display_order, is_active
        ) VALUES
            {pack_values}
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            pack_type = 'web_music',
            total_credits = EXCLUDED.total_credits,
            price_cents = EXCLUDED.price_cents,
            song_credits = EXCLUDED.song_credits,
            request_count = EXCLUDED.request_count,
            display_order = EXCLUDED.display_order,
            is_active = true,
            updated_at = NOW()
        """
    )
    # The old fourth pack no longer fits the recommended three-tier ladder.
    op.execute(
        """
        UPDATE credit_packs
        SET is_active = false, updated_at = NOW()
        WHERE slug = 'mega' AND pack_type = 'web_music'
        """
    )


def downgrade() -> None:
    # Restore the pre-127 web music plan prices/credits.
    op.execute(
        """
        UPDATE plans SET price_cents = 1000, monthly_credits = 1000, display_order = 1,
            updated_at = NOW()
        WHERE name IN ('starter_monthly', 'starter_yearly')
        """
    )
    op.execute(
        """
        UPDATE plans SET price_cents = 3000, monthly_credits = 3500, display_order = 2,
            updated_at = NOW()
        WHERE name IN ('creator_monthly', 'creator_yearly')
        """
    )
    op.execute(
        """
        UPDATE plans SET price_cents = 6000, monthly_credits = 8000, display_order = 3,
            updated_at = NOW()
        WHERE name IN ('studio_monthly', 'studio_yearly')
        """
    )
    op.execute(
        """
        UPDATE plans SET price_cents = 10200 WHERE name = 'starter_yearly'
        """
    )
    op.execute(
        """
        UPDATE plans SET price_cents = 30600 WHERE name = 'creator_yearly'
        """
    )
    op.execute("DELETE FROM plans WHERE name IN ('pro_monthly', 'pro_yearly')")

    op.execute(
        """
        UPDATE credit_packs SET total_credits = 400, price_cents = 500, song_credits = 40,
            request_count = 40, display_order = 1, updated_at = NOW()
        WHERE slug = 'small' AND pack_type = 'web_music'
        """
    )
    op.execute(
        """
        UPDATE credit_packs SET total_credits = 1000, price_cents = 1000, song_credits = 100,
            request_count = 100, display_order = 2, updated_at = NOW()
        WHERE slug = 'medium' AND pack_type = 'web_music'
        """
    )
    op.execute(
        """
        UPDATE credit_packs SET name = 'Large Pack', total_credits = 2500, price_cents = 2500,
            song_credits = 250, request_count = 250, display_order = 3, updated_at = NOW()
        WHERE slug = 'large' AND pack_type = 'web_music'
        """
    )
    op.execute(
        """
        UPDATE credit_packs SET is_active = true, updated_at = NOW()
        WHERE slug = 'mega' AND pack_type = 'web_music'
        """
    )
