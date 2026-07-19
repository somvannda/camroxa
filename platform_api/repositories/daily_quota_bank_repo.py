"""Repository for daily_quota_bank accrual and consumption."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4


class AsyncPGPool(Protocol):
    async def acquire(self) -> Any: ...

    async def fetchrow(self, query: str, *args: Any) -> Any: ...

    async def execute(self, query: str, *args: Any) -> str: ...


class DailyQuotaBankRepository:
    """Persist banked daily allowance per user/channel/operation."""

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def get_row(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
    ) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT banked_units, last_accrual_date
            FROM daily_quota_bank
            WHERE user_id = $1
              AND channel_profile_id IS NOT DISTINCT FROM $2
              AND operation_type = $3
            """,
            user_id,
            channel_profile_id,
            operation_type,
        )
        if row is None:
            return None
        return {
            "banked_units": int(row["banked_units"] or 0),
            "last_accrual_date": row.get("last_accrual_date"),
        }

    async def upsert_accrual(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        banked_units: int,
        last_accrual_date: date,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO daily_quota_bank (
                id, user_id, channel_profile_id, operation_type,
                banked_units, last_accrual_date, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (user_id, channel_profile_id, operation_type)
            DO UPDATE SET
                banked_units = EXCLUDED.banked_units,
                last_accrual_date = EXCLUDED.last_accrual_date,
                updated_at = NOW()
            """,
            uuid4(),
            user_id,
            channel_profile_id,
            operation_type,
            max(0, int(banked_units)),
            last_accrual_date,
        )

    async def decrement_bank(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        units: int,
    ) -> int:
        """Atomically decrement bank; returns remaining banked units."""
        if units <= 0:
            row = await self.get_row(user_id, channel_profile_id, operation_type)
            return int(row["banked_units"]) if row else 0

        acquire = getattr(self._pool, "acquire", None)
        if acquire is None:
            row = await self.get_row(user_id, channel_profile_id, operation_type)
            current = int(row["banked_units"]) if row else 0
            remaining = max(0, current - units)
            last_date = row.get("last_accrual_date") if row else None
            if last_date is not None:
                await self.upsert_accrual(
                    user_id,
                    channel_profile_id,
                    operation_type,
                    banked_units=remaining,
                    last_accrual_date=last_date,
                )
            return remaining

        async with acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT banked_units, last_accrual_date
                    FROM daily_quota_bank
                    WHERE user_id = $1
                      AND channel_profile_id IS NOT DISTINCT FROM $2
                      AND operation_type = $3
                    FOR UPDATE
                    """,
                    user_id,
                    channel_profile_id,
                    operation_type,
                )
                if row is None:
                    return 0
                remaining = max(0, int(row["banked_units"] or 0) - units)
                await conn.execute(
                    """
                    UPDATE daily_quota_bank
                    SET banked_units = $4, updated_at = NOW()
                    WHERE user_id = $1
                      AND channel_profile_id IS NOT DISTINCT FROM $2
                      AND operation_type = $3
                    """,
                    user_id,
                    channel_profile_id,
                    operation_type,
                    remaining,
                )
                return remaining
