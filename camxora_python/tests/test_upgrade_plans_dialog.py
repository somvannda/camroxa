"""Tests for the native credits-required dialog (packs-only billing)."""

from __future__ import annotations

from shared.models.auth import CreditPack
from features.account.views.upgrade_plans_dialog import (
    CREDITS_PER_SONG,
    PACK_VALIDITY_DAYS,
    credits_to_songs,
    format_subscription_price,
    pack_feature_lines,
)


def test_format_subscription_price() -> None:
    assert format_subscription_price(1000) == "$10.00"
    assert format_subscription_price(3000) == "$30.00"


def test_credits_to_songs() -> None:
    assert credits_to_songs(1000) == 200
    assert credits_to_songs(3500) == 700
    assert credits_to_songs(50) == 10


def test_pack_features_are_30_day_terms() -> None:
    pack = CreditPack(
        id="p1",
        slug="small",
        name="Small Pack",
        total_credits=1000,
        price_cents=500,
    )
    lines = pack_feature_lines(pack)
    assert f"Valid for {PACK_VALIDITY_DAYS} days from purchase" in lines
    assert "Buy again any time" in lines


def test_list_credit_packs_reads_v3_topups_catalog() -> None:
    from shared.services.platform_api import PlatformApi

    api = PlatformApi.__new__(PlatformApi)

    class _Client:
        def request(self, path, *_a, **_k):
            assert path == "/topups/packs"
            return {
                "packs": [
                    {
                        "id": "small",
                        "slug": "small",
                        "name": "Small Pack",
                        "description": "",
                        "total_credits": 1000,
                        "price_cents": 500,
                        "display_order": 1,
                        "songs_equivalent": 200,
                    },
                    {
                        "id": "medium",
                        "slug": "medium",
                        "name": "Medium Pack",
                        "description": "",
                        "total_credits": 2300,
                        "price_cents": 1000,
                        "display_order": 2,
                        "songs_equivalent": 460,
                    },
                    {
                        "id": "retired",
                        "slug": "retired",
                        "name": "Retired",
                        "total_credits": 0,
                        "price_cents": 0,
                        "display_order": 9,
                    },
                ]
            }

    api._client = _Client()  # type: ignore[attr-defined]
    packs = api.list_credit_packs()
    assert [p.name for p in packs] == ["Small Pack", "Medium Pack"]
    assert packs[0].total_credits == 1000
    assert credits_to_songs(packs[0].total_credits, CREDITS_PER_SONG) == 200
