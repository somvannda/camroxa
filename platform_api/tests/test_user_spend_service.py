"""Tests for admin User Spent rollup service."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.services.credit_units import CREDIT_SCALE
from platform_api.services.user_spend_service import UserSpendService


class _FakeSettings:
    async def get_global_credit_value(self) -> float | None:
        return 0.01


class _FakeModelCostRepo:
    async def get_all(self) -> list[dict[str, Any]]:
        return [
            {
                "ai_service": "suno",
                "operation_type": "music",
                "sub_model": "",
                "cost_usd": 0.06,
            }
        ]


class _FakeCreditRepo:
    def __init__(self) -> None:
        self.user_a = uuid4()
        self.user_b = uuid4()
        self.plan_id = uuid4()

    async def list_user_spend_cog_rows(self, **kwargs: Any) -> list[dict[str, Any]]:
        del kwargs
        return [
            {
                "user_id": self.user_a,
                "user_email": "heavy@example.com",
                "user_display_name": "Heavy",
                "operation": "music",
                "provider": "suno",
                "model": "",
                "events": 20,
                "wallet_charged_units": 10 * CREDIT_SCALE,
                "plan_included_list_units": 100 * CREDIT_SCALE,
                "soft_overage_events": 2,
            },
            {
                "user_id": self.user_b,
                "user_email": "light@example.com",
                "user_display_name": "Light",
                "operation": "music",
                "provider": "suno",
                "model": "",
                "events": 1,
                "wallet_charged_units": 0,
                "plan_included_list_units": 6 * CREDIT_SCALE,
                "soft_overage_events": 0,
            },
        ]

    async def list_active_plans_for_users(
        self, user_ids: list[UUID]
    ) -> dict[UUID, dict[str, Any]]:
        out: dict[UUID, dict[str, Any]] = {}
        for uid in user_ids:
            if uid == self.user_a:
                out[uid] = {
                    "user_id": uid,
                    "plan_id": self.plan_id,
                    "plan_name": "Pro",
                    "price_cents": 500,  # $5
                    "billing_cycle_days": 30,
                    "monthly_song_limit": 10,
                    "monthly_draft_limit": 100,
                    "monthly_image_limit": 50,
                    "monthly_video_limit": 10,
                    "monthly_merge_limit": 5,
                    "profile_allowance": 2,
                    "profile_addon_slots": 0,
                    "activated_at": datetime(2026, 8, 1),
                }
            # user_b stays Free
        return out

    async def list_monthly_meters_for_users(
        self, user_ids: list[UUID], *, period_start: Any
    ) -> dict[UUID, dict[str, int]]:
        del period_start
        out: dict[UUID, dict[str, int]] = {}
        for uid in user_ids:
            if uid == self.user_a:
                out[uid] = {"song": 12, "draft": 0, "image": 0, "video": 0, "merge": 0}
            else:
                out[uid] = {}
        return out

    async def get_all(self) -> list[dict[str, Any]]:
        return []


@pytest.mark.asyncio
async def test_user_spend_flags_over_allowance_and_margin_risk() -> None:
    repo = _FakeCreditRepo()
    service = UserSpendService(
        credit_repo=repo,
        model_cost_repo=_FakeModelCostRepo(),
        settings_service=_FakeSettings(),
    )

    result = await service.list_user_spend(
        from_date=datetime(2026, 8, 1),
        to_date=datetime(2026, 8, 31),
        sort="cogs_desc",
    )

    assert result.total == 2
    assert result.items[0].email == "heavy@example.com"
    # 20 events × $0.06 = $1.20 COGS; plan revenue ~$5 for full month → not margin risk
    # but song meter 12/10 is hot + soft overage → over allowance
    heavy = result.items[0]
    assert heavy.est_cogs_usd == pytest.approx(1.2)
    assert heavy.over_allowance is True
    assert "song" in heavy.meters_hot
    assert heavy.soft_overage_events == 2
    assert heavy.by_cog[0].operation == "music"

    light = next(u for u in result.items if u.email == "light@example.com")
    assert light.plan_name == "Free"
    # Free with $0.06 COGS below $1 floor → no margin risk
    assert light.margin_risk is False
    assert light.over_allowance is False


@pytest.mark.asyncio
async def test_user_spend_alert_filter_and_summary() -> None:
    repo = _FakeCreditRepo()
    service = UserSpendService(
        credit_repo=repo,
        model_cost_repo=_FakeModelCostRepo(),
        settings_service=_FakeSettings(),
    )

    result = await service.list_user_spend(
        from_date=datetime(2026, 8, 1),
        to_date=datetime(2026, 8, 31),
        alert="over_allowance",
    )
    assert result.total == 1
    assert result.items[0].email == "heavy@example.com"
    assert result.summary["users_over_allowance"] == 1
