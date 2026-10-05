"""Plan credit cadence: daily XOR monthly, and Free cadence read from the plan."""

from __future__ import annotations

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.plan_credits import validate_credit_cadence
from platform_api.services.v2.credit_service import CreditService


def test_rejects_both_daily_and_monthly() -> None:
    with pytest.raises(ValidationError):
        validate_credit_cadence(monthly_credits=50, daily_credits=50)


def test_allows_monthly_only() -> None:
    validate_credit_cadence(monthly_credits=50, daily_credits=0)


def test_allows_daily_only() -> None:
    validate_credit_cadence(monthly_credits=0, daily_credits=50)


def test_allows_neither() -> None:
    validate_credit_cadence(monthly_credits=0, daily_credits=0)


def test_allows_nulls() -> None:
    validate_credit_cadence(monthly_credits=None, daily_credits=None)


class _FakeDb:
    def __init__(self, row: object) -> None:
        self._row = row

    async def fetch_one(self, *_args: object, **_kwargs: object) -> object:
        return self._row


@pytest.mark.asyncio
async def test_free_reset_period_monthly_from_plan() -> None:
    service = CreditService(_FakeDb({"daily_credits": 0, "monthly_credits": 50}))
    assert await service.free_reset_period() == "monthly"


@pytest.mark.asyncio
async def test_free_reset_period_daily_from_plan() -> None:
    service = CreditService(_FakeDb({"daily_credits": 50, "monthly_credits": 0}))
    assert await service.free_reset_period() == "daily"


@pytest.mark.asyncio
async def test_free_reset_period_defaults_when_plan_missing() -> None:
    service = CreditService(_FakeDb(None))
    assert await service.free_reset_period() == "daily"
