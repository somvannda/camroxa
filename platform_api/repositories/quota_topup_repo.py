"""Repository for admin period-scoped plan quota top-ups."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol
from uuid import UUID, uuid4


class AsyncPGPool(Protocol):
    async def fetchrow(self, query: str, *args: Any) -> Any: ...

    async def fetch(self, query: str, *args: Any) -> list[Any]: ...

    async def execute(self, query: str, *args: Any) -> str: ...


class QuotaTopupRepository:
    """Append-only ledger of period quota limit bumps."""

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def add_topup(
        self,
        *,
        user_id: UUID,
        license_id: UUID | None,
        period_start: date,
        quota_kind: str,
        extra_units: int,
        reason: str,
        created_by: UUID,
    ) -> UUID:
        topup_id = uuid4()
        await self._pool.execute(
            """
            INSERT INTO user_period_quota_topups (
                id, user_id, license_id, period_start, quota_kind,
                extra_units, reason, created_by, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """,
            topup_id,
            user_id,
            license_id,
            period_start,
            quota_kind,
            int(extra_units),
            reason,
            created_by,
        )
        return topup_id

    async def sum_extra_units(
        self,
        user_id: UUID,
        period_start: date,
        quota_kind: str,
    ) -> int:
        row = await self._pool.fetchrow(
            """
            SELECT COALESCE(SUM(extra_units), 0)::int AS total
            FROM user_period_quota_topups
            WHERE user_id = $1
              AND period_start = $2
              AND quota_kind = $3
            """,
            user_id,
            period_start,
            quota_kind,
        )
        return int(row["total"] or 0) if row else 0

    async def sum_extras_for_period(
        self,
        user_id: UUID,
        period_start: date,
    ) -> dict[str, int]:
        rows = await self._pool.fetch(
            """
            SELECT quota_kind, COALESCE(SUM(extra_units), 0)::int AS total
            FROM user_period_quota_topups
            WHERE user_id = $1
              AND period_start = $2
            GROUP BY quota_kind
            """,
            user_id,
            period_start,
        )
        return {str(row["quota_kind"]): int(row["total"] or 0) for row in rows}

    async def list_for_period(
        self,
        user_id: UUID,
        period_start: date,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, license_id, period_start, quota_kind, extra_units,
                   reason, created_by, created_at
            FROM user_period_quota_topups
            WHERE user_id = $1
              AND period_start = $2
            ORDER BY created_at DESC
            """,
            user_id,
            period_start,
        )
        return [dict(row) for row in rows]
