"""Tests for daily quota bank accrual and consumption."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.services.daily_quota_bank_service import (
    DailyQuotaBankService,
    bank_units_for_consumption,
)


class FakeBankRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, UUID | None, str], dict[str, Any]] = {}
        self.decrements: list[int] = []

    async def get_row(
        self, user_id: UUID, channel_profile_id: UUID | None, operation_type: str
    ) -> dict[str, Any] | None:
        return self.rows.get((user_id, channel_profile_id, operation_type))

    async def upsert_accrual(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        banked_units: int,
        last_accrual_date: date,
    ) -> None:
        self.rows[(user_id, channel_profile_id, operation_type)] = {
            "banked_units": banked_units,
            "last_accrual_date": last_accrual_date,
        }

    async def decrement_bank(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        units: int,
    ) -> int:
        self.decrements.append(units)
        key = (user_id, channel_profile_id, operation_type)
        row = self.rows.get(key, {"banked_units": 0, "last_accrual_date": None})
        remaining = max(0, int(row["banked_units"]) - units)
        row["banked_units"] = remaining
        self.rows[key] = row
        return remaining


class FakeUsageRepo:
    def __init__(self) -> None:
        self._daily: dict[tuple[UUID, UUID | None, str, date], int] = {}

    def set_daily(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        count: int,
    ) -> None:
        self._daily[(user_id, channel_profile_id, operation_type, usage_date)] = count

    async def get_daily_count(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> int:
        return self._daily.get(
            (user_id, channel_profile_id, operation_type, usage_date), 0
        )


def test_bank_units_for_consumption_math() -> None:
    assert bank_units_for_consumption(daily_count_before=6, count=3, daily_limit=7) == 2
    assert bank_units_for_consumption(daily_count_before=3, count=2, daily_limit=7) == 0
    assert bank_units_for_consumption(daily_count_before=8, count=1, daily_limit=7) == 1


@pytest.mark.asyncio
async def test_accrue_unused_daily_allowance(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.services import billing_calendar

    today = date(2026, 7, 17)
    monkeypatch.setattr(billing_calendar, "billing_today", lambda: today)

    user_id = uuid4()
    channel_id = uuid4()
    bank_repo = FakeBankRepo()
    usage_repo = FakeUsageRepo()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    usage_repo.set_daily(user_id, channel_id, "music", yesterday, 2)
    usage_repo.set_daily(user_id, channel_id, "music", two_days_ago, 7)

    service = DailyQuotaBankService(bank_repo, usage_repo)
    banked = await service.accrue_and_get_banked_units(
        user_id,
        channel_id,
        "music",
        daily_limit=7,
    )

    assert banked == 5 + 0
    row = bank_repo.rows[(user_id, channel_id, "music")]
    assert row["last_accrual_date"] == yesterday


@pytest.mark.asyncio
async def test_consume_bank_after_daily_allowance_exhausted() -> None:
    user_id = uuid4()
    channel_id = uuid4()
    bank_repo = FakeBankRepo()
    bank_repo.rows[(user_id, channel_id, "music")] = {
        "banked_units": 10,
        "last_accrual_date": date(2026, 7, 16),
    }
    usage_repo = FakeUsageRepo()
    service = DailyQuotaBankService(bank_repo, usage_repo)

    remaining = await service.consume_bank_for_usage(
        user_id,
        channel_id,
        "music",
        daily_count_before=6,
        count=3,
        daily_limit=7,
    )

    assert remaining == 8
    assert bank_repo.decrements == [2]
    assert bank_repo.rows[(user_id, channel_id, "music")]["banked_units"] == 8
