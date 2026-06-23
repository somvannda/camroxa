"""Usage tracking repository for daily and monthly operation counts.

Provides atomic upsert-based increment operations for tracking usage per
user, channel, and operation type. Uses PostgreSQL's ON CONFLICT ... DO UPDATE
pattern to maintain running daily and monthly counters in a single row per
(user, channel, operation, date) partition.

Requirements: 6.5, 6.6, 7.5
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Protocol
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single row."""
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return all rows."""
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single value."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        ...


class UsageTrackingRepository:
    """Repository for usage_tracking table operations.

    Tracks daily and monthly usage counts per user, channel profile, and
    operation type. Supports atomic increments via PostgreSQL UPSERT to
    prevent lost updates under concurrent access.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def get_daily_count(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> int:
        """Return the daily usage count for a specific partition.

        Args:
            user_id: The UUID of the user.
            channel_profile_id: The UUID of the channel profile, or None
                for operations not scoped to a channel.
            operation_type: The type of operation (e.g. "music_generation").
            usage_date: The date to query usage for.

        Returns:
            The current daily count, or 0 if no record exists.
        """
        row = await self._pool.fetchval(
            """
            SELECT daily_count
            FROM usage_tracking
            WHERE user_id = $1
              AND channel_profile_id IS NOT DISTINCT FROM $2
              AND operation_type = $3
              AND usage_date = $4
            """,
            user_id,
            channel_profile_id,
            operation_type,
            usage_date,
        )
        return row if row is not None else 0

    async def get_monthly_count(
        self,
        user_id: UUID,
        operation_type: str,
        period_start: date,
    ) -> int:
        """Return the total monthly usage count for a user and operation type.

        Sums monthly_count across all channel profiles for the given
        operation type within the billing period starting at period_start.

        Args:
            user_id: The UUID of the user.
            operation_type: The type of operation (e.g. "music_generation").
            period_start: The start date of the billing period.

        Returns:
            The total monthly count across all channels, or 0 if no
            records exist.
        """
        row = await self._pool.fetchval(
            """
            SELECT COALESCE(SUM(monthly_count), 0)
            FROM usage_tracking
            WHERE user_id = $1
              AND operation_type = $2
              AND period_start_date = $3
            """,
            user_id,
            operation_type,
            period_start,
        )
        return int(row) if row is not None else 0

    async def increment_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        period_start: date,
    ) -> None:
        """Atomically increment daily and monthly usage counters.

        Uses INSERT ... ON CONFLICT DO UPDATE to either create a new
        tracking record or increment the existing one's counters. This
        is safe under concurrent access due to PostgreSQL's row-level
        locking on conflict resolution.

        Args:
            user_id: The UUID of the user.
            channel_profile_id: The UUID of the channel profile, or None
                for operations not scoped to a channel.
            operation_type: The type of operation (e.g. "music_generation").
            usage_date: The date of the usage event.
            period_start: The start date of the current billing period.
        """
        new_id = uuid4()
        await self._pool.execute(
            """
            INSERT INTO usage_tracking (
                id, user_id, channel_profile_id, operation_type,
                usage_date, daily_count, monthly_count,
                period_start_date, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, 1, 1, $6, NOW(), NOW()
            )
            ON CONFLICT (user_id, channel_profile_id, operation_type, usage_date)
            DO UPDATE SET
                daily_count = usage_tracking.daily_count + 1,
                monthly_count = usage_tracking.monthly_count + 1,
                updated_at = NOW()
            """,
            new_id,
            user_id,
            channel_profile_id,
            operation_type,
            usage_date,
            period_start,
        )
