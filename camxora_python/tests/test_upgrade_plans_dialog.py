"""Tests for native Music-style upgrade plans dialog helpers."""

from __future__ import annotations

from shared.models.auth import WebMusicSubscriptionPlan
from features.account.views.upgrade_plans_dialog import (
    calculate_yearly_discount,
    credits_to_songs,
    format_plan_display_name,
    format_subscription_price,
    plan_feature_lines,
)


def test_format_subscription_price() -> None:
    assert format_subscription_price(1000) == "$10.00"
    assert format_subscription_price(3000) == "$30.00"


def test_credits_to_songs() -> None:
    assert credits_to_songs(1000) == 200
    assert credits_to_songs(3500) == 700
    assert credits_to_songs(50) == 10


def test_format_plan_display_name() -> None:
    assert format_plan_display_name("starter_monthly") == "Starter (Monthly)"
    assert format_plan_display_name("Creator (Yearly)") == "Creator (Yearly)"


def test_calculate_yearly_discount() -> None:
    assert calculate_yearly_discount(1000, 10200) == 15


def test_plan_feature_fallback() -> None:
    plan = WebMusicSubscriptionPlan(
        id="p1",
        name="starter_monthly",
        price_cents=1000,
        billing_cycle="monthly",
        monthly_credits=1000,
        features=[],
    )
    lines = plan_feature_lines(plan)
    assert "Web Create" in lines
    assert "Desktop studio" in lines


def test_list_web_music_plans_falls_back_to_public_catalog(monkeypatch) -> None:
    from shared.models.auth import PublicPlan
    from shared.services.platform_api import PlatformApi

    api = PlatformApi.__new__(PlatformApi)

    def boom(*_a, **_k):
        raise RuntimeError("v2 missing")

    monkeypatch.setattr(
        api,
        "list_public_plans",
        lambda: [
            PublicPlan(
                id="free",
                name="Free",
                price_cents=0,
                effective_price_cents=0,
                billing_cycle_days=30,
                monthly_credits=0,
                daily_credits=50,
            ),
            PublicPlan(
                id="s",
                name="starter_monthly",
                price_cents=1000,
                effective_price_cents=1000,
                billing_cycle_days=30,
                monthly_credits=1000,
            ),
            PublicPlan(
                id="c",
                name="creator_monthly",
                price_cents=3000,
                effective_price_cents=3000,
                billing_cycle_days=30,
                monthly_credits=3500,
            ),
            PublicPlan(
                id="st",
                name="studio_monthly",
                price_cents=6000,
                effective_price_cents=6000,
                billing_cycle_days=30,
                monthly_credits=8000,
            ),
        ],
    )

    class _Client:
        def request(self, *_a, **_k):
            raise boom()

    api._client = _Client()  # type: ignore[attr-defined]
    plans = api.list_web_music_subscription_plans()
    assert len(plans) == 3
    assert {p.name for p in plans} == {
        "starter_monthly",
        "creator_monthly",
        "studio_monthly",
    }


def test_list_web_music_plans_uses_v3_subscriptions_catalog() -> None:
    from shared.services.platform_api import PlatformApi

    api = PlatformApi.__new__(PlatformApi)

    class _Client:
        def request(self, path, *_a, **_k):
            assert path == "/subscriptions/plans"
            return {
                "plans": [
                    {
                        "id": "s",
                        "name": "starter_monthly",
                        "price_cents": 1000,
                        "billing_cycle": "monthly",
                        "monthly_credits": 1000,
                        "is_public": True,
                    },
                    {
                        "id": "free",
                        "name": "Free",
                        "price_cents": 0,
                        "billing_cycle": "monthly",
                        "monthly_credits": 0,
                        "is_public": True,
                    },
                ]
            }

    api._client = _Client()  # type: ignore[attr-defined]
    plans = api.list_web_music_subscription_plans()
    assert [p.name for p in plans] == ["starter_monthly"]
