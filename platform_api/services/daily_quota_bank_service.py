"""Accrue and consume banked daily plan allowance."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Protocol
from uuid import UUID

from platform_api.services.billing_calendar import billing_today


class DailyQuotaBankRepoProtocol(Protocol):
    async def get_row(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
    ) -> dict[str, Any] | None: ...

    async def upsert_accrual(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        banked_units: int,
        last_accrual_date: date,
    ) -> None: ...

    async def decrement_bank(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        units: int,
    ) -> int: ...


class UsageDailyCountProtocol(Protocol):
    async def get_daily_count(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> int: ...

    async def get_account_daily_count(
        self, user_id: UUID, operation_type: str, usage_date: date
    ) -> int: ...


def bank_units_for_consumption(
    *,
    daily_count_before: int,
    count: int,
    daily_limit: int,
) -> int:
    """Units drawn from bank when today's allowance is already partially used."""
    if count <= 0 or daily_limit <= 0:
        return 0
    return max(0, min(count, daily_count_before + count - daily_limit))


class DailyQuotaBankService:
    """Bank unused daily allowance for returning subscribers."""

    def __init__(
        self,
        bank_repo: DailyQuotaBankRepoProtocol,
        usage_repo: UsageDailyCountProtocol,
    ) -> None:
        self._bank_repo = bank_repo
        self._usage_repo = usage_repo

    async def accrue_and_get_banked_units(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        daily_limit: int,
        usage_date: date | None = None,
        account_daily: bool = False,
    ) -> int:
        """Accrue missed complete billing days up to yesterday; return bank balance."""
        if daily_limit <= 0:
            return 0

        today = usage_date or billing_today()
        yesterday = today - timedelta(days=1)
        row = await self._bank_repo.get_row(
            user_id, channel_profile_id, operation_type
        )
        banked = int(row["banked_units"]) if row else 0
        last_accrual: date | None = row.get("last_accrual_date") if row else None

        if last_accrual is None:
            last_accrual = yesterday - timedelta(days=1)

        cursor = last_accrual + timedelta(days=1)
        while cursor <= yesterday:
            usage_on_day = await self._daily_usage(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                usage_date=cursor,
                account_daily=account_daily,
            )
            banked += max(0, daily_limit - usage_on_day)
            cursor += timedelta(days=1)

        if cursor > last_accrual + timedelta(days=1) or row is None:
            await self._bank_repo.upsert_accrual(
                user_id,
                channel_profile_id,
                operation_type,
                banked_units=banked,
                last_accrual_date=yesterday,
            )

        return banked

    async def consume_bank_for_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        daily_count_before: int,
        count: int,
        daily_limit: int,
    ) -> int:
        """Decrement bank after a successful plan-quota reservation."""
        units = bank_units_for_consumption(
            daily_count_before=daily_count_before,
            count=count,
            daily_limit=daily_limit,
        )
        if units <= 0:
            return 0
        return await self._bank_repo.decrement_bank(
            user_id,
            channel_profile_id,
            operation_type,
            units=units,
        )

    async def _daily_usage(
        self,
        *,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        account_daily: bool,
    ) -> int:
        if account_daily:
            getter = getattr(self._usage_repo, "get_account_daily_count", None)
            if getter is not None:
                return int(await getter(user_id, operation_type, usage_date))
        return await self._usage_repo.get_daily_count(
            user_id, channel_profile_id, operation_type, usage_date
        )
