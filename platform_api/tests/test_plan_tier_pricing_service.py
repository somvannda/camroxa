"""Tests for channel-tier pricing and profile add-on quotes."""

from __future__ import annotations

import pytest

from platform_api.services.plan_tier_pricing_service import (
    PlanQuotaTemplate,
    PROFILE_ADDON_STEP,
    billing_term_quotes,
    build_tier_monthly_prices,
    combined_billing_term_quotes,
    find_profile_addon_plan,
    find_two_channel_monthly_base,
    quote_profile_addon_from_plan,
    round_whole_dollars,
    scale_plan_quotas,
    tier_monthly_price_cents,
)

BASE_CENTS = 7900
BASE_CHANNELS = 2


def test_tier_monthly_price_scales_linearly() -> None:
    six = tier_monthly_price_cents(BASE_CENTS, base_channels=BASE_CHANNELS, target_channels=6)
    ten = tier_monthly_price_cents(BASE_CENTS, base_channels=BASE_CHANNELS, target_channels=10)
    assert six == BASE_CENTS * 3
    assert ten == BASE_CENTS * 5
    assert six < ten


def test_round_whole_dollars_ceils_to_whole_dollar() -> None:
    assert round_whole_dollars(7901) == 8000
    assert round_whole_dollars(7900) == 7900


def test_scale_plan_quotas_triples_for_six_channels() -> None:
    template = PlanQuotaTemplate(
        profile_allowance=2,
        monthly_song_limit=300,
        monthly_image_limit=120,
        monthly_draft_limit=1260,
        monthly_video_limit=300,
        monthly_merge_limit=30,
        daily_song_limit_per_channel=10,
        daily_image_limit_per_channel=2,
        daily_draft_limit_per_channel=21,
        daily_video_limit=10,
        daily_merge_limit=1,
    )
    scaled = scale_plan_quotas(template, 6)
    assert scaled.profile_allowance == 6
    assert scaled.monthly_song_limit == 900
    assert scaled.monthly_image_limit == 360
    assert scaled.daily_song_limit_per_channel == 10


def test_profile_addon_is_fixed_price_from_plan_row() -> None:
    addon_plan = type(
        "Plan",
        (),
        {"price_cents": 7900, "profile_allowance": 2, "plan_kind": "profile_addon", "is_active": True},
    )()
    for current in (2, 4, 6, 8):
        quote = quote_profile_addon_from_plan(
            current_channels=current,
            addon_channels=PROFILE_ADDON_STEP,
            addon_plan=addon_plan,
        )
        assert quote.monthly_addon_cents == 7900


def test_find_profile_addon_plan_prefers_matching_bundle() -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    from platform_api.models.domain import Plan

    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    addon = Plan(
        id=uuid4(),
        name="Add-on · +2 channels",
        price_cents=7900,
        billing_cycle_days=30,
        profile_allowance=2,
        plan_kind="profile_addon",
        is_active=True,
        effective_from=now,
        created_at=now,
        updated_at=now,
    )
    found = find_profile_addon_plan([addon], 2)
    assert found is not None
    assert found.price_cents == 7900


def test_profile_addon_requires_pairs() -> None:
    with pytest.raises(ValueError):
        from platform_api.services.plan_tier_pricing_service import quote_profile_addon_monthly

        quote_profile_addon_monthly(
            current_channels=2,
            addon_channels=1,
            base_monthly_cents=BASE_CENTS,
        )


def test_billing_term_quotes_apply_discounts_with_whole_dollars() -> None:
    quotes = billing_term_quotes(10_000)
    monthly, semi, annual = quotes
    assert monthly.total_cents == 10_000
    assert semi.total_cents == 51_000
    assert annual.total_cents == 90_000
    assert semi.billing_cycle_days == 180
    assert annual.billing_cycle_days == 365


def test_combined_billing_term_quotes_use_plan_plus_addon() -> None:
    quotes = combined_billing_term_quotes(plan_monthly_cents=7900, addon_monthly_cents=7900)
    semi = quotes[1]
    assert semi.total_cents == round_whole_dollars(int(round(15_800 * 6 * 0.85)))


def test_build_tier_monthly_prices_linear() -> None:
    prices = build_tier_monthly_prices(BASE_CENTS, base_channels=BASE_CHANNELS)
    assert prices[2] == 7900
    assert prices[6] == 23700
    assert prices[10] == 39500


def test_find_two_channel_monthly_base_prefers_cheapest_active_plan() -> None:
    from datetime import datetime, timezone

    from platform_api.models.domain import Plan
    from uuid import uuid4

    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    expensive = Plan(
        id=uuid4(),
        name="Monthly · 2-channel",
        price_cents=9900,
        billing_cycle_days=30,
        profile_allowance=2,
        plan_kind="subscription",
        monthly_song_limit=420,
        monthly_image_limit=120,
        daily_song_limit_per_channel=7,
        daily_image_limit_per_channel=7,
        is_active=True,
        effective_from=now,
        created_at=now,
        updated_at=now,
    )
    base = Plan(
        id=uuid4(),
        name="Monthly · 2-channel promo",
        price_cents=7900,
        billing_cycle_days=30,
        profile_allowance=2,
        plan_kind="subscription",
        monthly_song_limit=420,
        monthly_image_limit=120,
        daily_song_limit_per_channel=7,
        daily_image_limit_per_channel=7,
        is_active=True,
        effective_from=now,
        created_at=now,
        updated_at=now,
    )
    inactive = Plan(
        id=uuid4(),
        name="Monthly · 2-channel old",
        price_cents=100,
        billing_cycle_days=30,
        profile_allowance=2,
        monthly_song_limit=420,
        monthly_image_limit=120,
        daily_song_limit_per_channel=7,
        daily_image_limit_per_channel=7,
        is_active=False,
        effective_from=now,
        created_at=now,
        updated_at=now,
    )

    found = find_two_channel_monthly_base([expensive, base, inactive])
    assert found is not None
    assert found.price_cents == 7900
