"""Phase 2: soft overage wallet hold before provider."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import InsufficientCreditsError
from platform_api.services.usage_enforcement_service import (
    OperationHold,
    UsageEnforcementService,
)


class _FakePricingRepo:
    def __init__(self, units: int = 50_000) -> None:
        self.units = units

    async def get_by_service_and_operation(self, *args, **kwargs):
        return {
            "credits_per_operation": self.units,
            "external_cost_cents": self.units,
        }


@pytest.mark.asyncio
async def test_reserve_and_hold_escrows_wallet_on_soft_overage(monkeypatch) -> None:
    user_id = uuid4()
    credit_repo = AsyncMock()
    credit_repo.atomic_deduct = AsyncMock(return_value=True)
    credit_repo.get_balance = AsyncMock(return_value=100_000)
    usage_repo = AsyncMock()
    usage_repo.get_monthly_count = AsyncMock(return_value=120)

    service = UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=usage_repo,
        plan_repo=AsyncMock(),
        pricing_repo=_FakePricingRepo(50_000),
        redis=AsyncMock(),
    )
    service.reserve_operation_quota = AsyncMock()
    service.release_operation_quota = AsyncMock()
    service._resolve_subscription_context = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            plan=SimpleNamespace(
                name="monthly",
                billing_cycle_days=30,
                monthly_song_limit=300,
                monthly_image_limit=120,
                monthly_draft_limit=1260,
                price_cents=7900,
            ),
            license_id=uuid4(),
            started_at=date.today(),
        )
    )
    service._period_start = lambda *_a, **_k: date.today()  # type: ignore[method-assign]

    async def _covers(**kwargs):
        return False  # soft overage

    monkeypatch.setattr(
        "platform_api.services.usage_enforcement_service.subscription_covers_operation",
        _covers,
    )

    hold = await service.reserve_and_hold_before_provider(
        user_id,
        uuid4(),
        "background_image",
        hold_credit_units=50_000,
        ai_service="fal",
        sub_model="flux",
    )
    assert hold == OperationHold(held_units=50_000, plan_covered=False)
    credit_repo.atomic_deduct.assert_awaited_once()
    assert credit_repo.atomic_deduct.await_args.args[1] == 50_000


@pytest.mark.asyncio
async def test_reserve_and_hold_plan_path_skips_wallet(monkeypatch) -> None:
    user_id = uuid4()
    credit_repo = AsyncMock()
    credit_repo.atomic_deduct = AsyncMock(return_value=True)

    service = UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=AsyncMock(),
        plan_repo=AsyncMock(),
        pricing_repo=_FakePricingRepo(),
        redis=AsyncMock(),
    )
    service.reserve_operation_quota = AsyncMock()
    service._resolve_subscription_context = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            plan=SimpleNamespace(
                name="monthly",
                billing_cycle_days=30,
                monthly_song_limit=300,
                monthly_image_limit=120,
                monthly_draft_limit=1260,
                price_cents=7900,
            ),
            license_id=uuid4(),
            started_at=date.today(),
        )
    )
    service._period_start = lambda *_a, **_k: date.today()  # type: ignore[method-assign]

    async def _covers(**kwargs):
        return True

    monkeypatch.setattr(
        "platform_api.services.usage_enforcement_service.subscription_covers_operation",
        _covers,
    )

    hold = await service.reserve_and_hold_before_provider(
        user_id,
        None,
        "background_image",
        hold_credit_units=50_000,
        ai_service="fal",
    )
    assert hold.plan_covered is True
    assert hold.held_units == 0
    credit_repo.atomic_deduct.assert_not_awaited()


@pytest.mark.asyncio
async def test_reserve_and_hold_rolls_back_quota_when_wallet_empty(monkeypatch) -> None:
    user_id = uuid4()
    credit_repo = AsyncMock()
    credit_repo.atomic_deduct = AsyncMock(return_value=False)
    credit_repo.get_balance = AsyncMock(return_value=0)

    service = UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=AsyncMock(),
        plan_repo=AsyncMock(),
        pricing_repo=_FakePricingRepo(),
        redis=AsyncMock(),
    )
    service.reserve_operation_quota = AsyncMock()
    service.release_operation_quota = AsyncMock()
    service._resolve_subscription_context = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._period_start = lambda *_a, **_k: date.today()  # type: ignore[method-assign]

    with pytest.raises(InsufficientCreditsError):
        await service.reserve_and_hold_before_provider(
            user_id,
            None,
            "background_image",
            hold_credit_units=50_000,
            ai_service="fal",
        )
    service.release_operation_quota.assert_awaited_once()
