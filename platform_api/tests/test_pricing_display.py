from platform_api.services.pricing_display import (
    credit_reset_label,
    credits_to_songs,
    normalize_pricing_features,
    resolve_pricing_credit_lines,
    resolve_pricing_features,
)


def test_credits_to_songs_counts_two_versions_per_generate() -> None:
    assert credits_to_songs(50) == 10
    assert credits_to_songs(1000) == 200
    assert credits_to_songs(3500) == 700
    assert credits_to_songs(8000) == 1600
    assert credits_to_songs(15) == 2
    assert credits_to_songs(9) == 0
    assert credits_to_songs(1000, credits_per_generate=8) == 250
    assert credits_to_songs(1000, credits_per_generate=0) == 200


def test_normalize_pricing_features_splits_and_trims() -> None:
    assert normalize_pricing_features("Web Create\n\n Top-up packs \nWeb Create") == [
        "Web Create",
        "Top-up packs",
    ]


def test_resolve_pricing_features_falls_back_by_plan_kind() -> None:
    assert resolve_pricing_features([], name="Free", price_cents=0, daily_credits=50) == [
        "Web Create",
        "Daily credit reset",
        "Top-up packs",
    ]
    assert resolve_pricing_features([], name="Starter", price_cents=1000) == [
        "Web Create",
        "Desktop studio",
        "Dual channels",
        "Top-up packs",
    ]
    assert resolve_pricing_features(["Custom line"], name="Starter", price_cents=1000) == [
        "Custom line"
    ]
    assert resolve_pricing_features([], name="Free", price_cents=0, daily_credits=0) == [
        "Web Create",
        "Top-up packs",
    ]
    assert resolve_pricing_features(
        [], name="Free", price_cents=0, daily_credits=0, monthly_credits=50
    ) == [
        "Web Create",
        "Monthly credit reset",
        "Top-up packs",
    ]


def test_credit_reset_label_follows_grant_period() -> None:
    assert credit_reset_label(daily_credits=50, monthly_credits=0) == "Credit reset daily"
    assert credit_reset_label(daily_credits=0, monthly_credits=50) == "Credit reset monthly"
    assert credit_reset_label(daily_credits=50, monthly_credits=50) == "Credit reset daily"
    assert credit_reset_label(daily_credits=0, monthly_credits=0) is None


def test_resolve_pricing_credit_lines_follows_daily_then_monthly() -> None:
    assert resolve_pricing_credit_lines([], daily_credits=50, monthly_credits=0) == [
        "daily credits",
        "≈ 10 songs/day",
        "Resets at midnight",
    ]
    assert resolve_pricing_credit_lines([], daily_credits=0, monthly_credits=1000) == [
        "credits per month",
        "≈ 200 songs/mo",
    ]
    assert resolve_pricing_credit_lines([], daily_credits=0, monthly_credits=0) == ["credits"]
    assert resolve_pricing_credit_lines(["Custom unit", "Custom hint"], daily_credits=50) == [
        "Custom unit",
        "Custom hint",
    ]
    assert resolve_pricing_credit_lines([], monthly_credits=1000, credits_per_generate=8) == [
        "credits per month",
        "≈ 250 songs/mo",
    ]
