"""Batch preflight must not touch plan-era tables dropped by migration 174.

`POST /api/v3/batches` returned 500 for every user after the credits-only
migration dropped ``user_period_quota_topups``: preflight fetched plan quota
top-up extras unconditionally, so asyncpg raised UndefinedTableError before the
wallet check ever ran.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.usage_enforcement_service import UsageEnforcementService


def _service(topup_service: AsyncMock, credit_repo: AsyncMock) -> UsageEnforcementService:
    return UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=AsyncMock(),
        plan_repo=AsyncMock(),
        pricing_repo=AsyncMock(),
        redis=AsyncMock(),
        quota_topup_service=topup_service,
    )


@pytest.mark.asyncio
async def test_preflight_batch_cost_skips_retired_quota_topup_lookup() -> None:
    """No plan (credits-only) means no quota top-ups to fetch."""
    credit_repo = AsyncMock()
    credit_repo.get_balance = AsyncMock(return_value=100_000)
    topup_service = AsyncMock()
    topup_service.extras_for_period = AsyncMock(return_value={"song": 5})

    service = _service(topup_service, credit_repo)
    service.enforce_fail_absorb_budget = AsyncMock()  # type: ignore[method-assign]

    await service.preflight_batch_cost(uuid4(), song_count=5, total_wallet_cost=1000)

    topup_service.extras_for_period.assert_not_awaited()
    credit_repo.get_balance.assert_awaited()


@pytest.mark.asyncio
async def test_preflight_batch_cost_still_enforces_wallet_balance() -> None:
    """The credit gate still runs when plan-era top-ups are skipped."""
    from platform_api.exceptions import InsufficientCreditsError

    credit_repo = AsyncMock()
    credit_repo.get_balance = AsyncMock(return_value=10)
    topup_service = AsyncMock()

    service = _service(topup_service, credit_repo)
    service.enforce_fail_absorb_budget = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(InsufficientCreditsError):
        await service.preflight_batch_cost(uuid4(), song_count=5, total_wallet_cost=1000)
