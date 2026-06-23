"""Unit tests for UsageTrackingRepository.

Tests daily/monthly count queries and atomic upsert increments using
an in-memory fake asyncpg pool that simulates the usage_tracking table.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.repositories.usage_tracking_repo import UsageTrackingRepository


# ---------------------------------------------------------------------------
# Fake asyncpg primitives
# ---------------------------------------------------------------------------


class FakeRecord(dict):
    """Simulates an asyncpg Record with dict-style access."""

    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(key)


class FakeAsyncPGPool:
    """In-memory asyncpg pool simulating the usage_tracking table.

    Stores rows keyed by (user_id, channel_profile_id, operation_type, usage_date).
    """

    def __init__(self) -> None:
        # Key: (user_id, channel_profile_id, operation_type, usage_date)
        # Value: {"daily_count": int, "monthly_count": int, "period_start_date": date}
        self._rows: dict[tuple[UUID, UUID | None, str, date], dict[str, Any]] = {}

    async def fetchrow(self, query: str, *args: Any) -> FakeRecord | None:
        return await self._handle_query(query, args, mode="fetchrow")

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._handle_query(query, args, mode="fetchval")

    async def fetch(self, query: str, *args: Any) -> list[FakeRecord]:
        return await self._handle_query(query, args, mode="fetch")

    async def execute(self, query: str, *args: Any) -> str:
        return await self._handle_query(query, args, mode="execute")

    async def _handle_query(self, query: str, args: tuple, mode: str) -> Any:
        q = query.strip().lower()

        # SELECT daily_count ... IS NOT DISTINCT FROM
        if "select daily_count" in q and "is not distinct from" in q:
            user_id = args[0]
            channel_profile_id = args[1]
            operation_type = args[2]
            usage_date = args[3]
            key = (user_id, channel_profile_id, operation_type, usage_date)
            row = self._rows.get(key)
            if mode == "fetchval":
                return row["daily_count"] if row else None
            if row:
                return FakeRecord({"daily_count": row["daily_count"]})
            return None

        # SELECT COALESCE(SUM(monthly_count), 0) ...
        if "coalesce(sum(monthly_count)" in q:
            user_id = args[0]
            operation_type = args[1]
            period_start = args[2]
            total = sum(
                v["monthly_count"]
                for (uid, _, op, _), v in self._rows.items()
                if uid == user_id
                and op == operation_type
                and v["period_start_date"] == period_start
            )
            if mode == "fetchval":
                return total
            return FakeRecord({"coalesce": total})

        # INSERT INTO usage_tracking ... ON CONFLICT ...
        if "insert into usage_tracking" in q and "on conflict" in q:
            # args: new_id, user_id, channel_profile_id, operation_type,
            #        usage_date, period_start
            _new_id = args[0]
            user_id = args[1]
            channel_profile_id = args[2]
            operation_type = args[3]
            usage_date = args[4]
            period_start = args[5]
            key = (user_id, channel_profile_id, operation_type, usage_date)
            if key in self._rows:
                self._rows[key]["daily_count"] += 1
                self._rows[key]["monthly_count"] += 1
            else:
                self._rows[key] = {
                    "daily_count": 1,
                    "monthly_count": 1,
                    "period_start_date": period_start,
                }
            return "INSERT 0 1"

        raise NotImplementedError(f"Unhandled query: {query}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pool() -> FakeAsyncPGPool:
    return FakeAsyncPGPool()


@pytest.fixture
def repo(pool: FakeAsyncPGPool) -> UsageTrackingRepository:
    return UsageTrackingRepository(pool)


# ---------------------------------------------------------------------------
# Tests — get_daily_count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_count_returns_zero_when_no_record(
    repo: UsageTrackingRepository,
) -> None:
    """Returns 0 when no usage record exists for the partition."""
    user_id = uuid4()
    channel_id = uuid4()
    count = await repo.get_daily_count(
        user_id, channel_id, "music_generation", date(2024, 6, 15)
    )
    assert count == 0


@pytest.mark.asyncio
async def test_get_daily_count_returns_existing_count(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Returns the stored daily_count for an existing record."""
    user_id = uuid4()
    channel_id = uuid4()
    key = (user_id, channel_id, "music_generation", date(2024, 6, 15))
    pool._rows[key] = {
        "daily_count": 5,
        "monthly_count": 20,
        "period_start_date": date(2024, 6, 1),
    }
    count = await repo.get_daily_count(
        user_id, channel_id, "music_generation", date(2024, 6, 15)
    )
    assert count == 5


@pytest.mark.asyncio
async def test_get_daily_count_with_none_channel(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Handles NULL channel_profile_id correctly (IS NOT DISTINCT FROM)."""
    user_id = uuid4()
    key = (user_id, None, "text_generation", date(2024, 6, 15))
    pool._rows[key] = {
        "daily_count": 3,
        "monthly_count": 10,
        "period_start_date": date(2024, 6, 1),
    }
    count = await repo.get_daily_count(
        user_id, None, "text_generation", date(2024, 6, 15)
    )
    assert count == 3


# ---------------------------------------------------------------------------
# Tests — get_monthly_count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_monthly_count_returns_zero_when_no_records(
    repo: UsageTrackingRepository,
) -> None:
    """Returns 0 when no usage records exist for the period."""
    user_id = uuid4()
    count = await repo.get_monthly_count(
        user_id, "image_generation", date(2024, 6, 1)
    )
    assert count == 0


@pytest.mark.asyncio
async def test_get_monthly_count_sums_across_channels(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Sums monthly_count across all channels for the operation type."""
    user_id = uuid4()
    channel_a = uuid4()
    channel_b = uuid4()
    period_start = date(2024, 6, 1)

    pool._rows[(user_id, channel_a, "image_generation", date(2024, 6, 5))] = {
        "daily_count": 2,
        "monthly_count": 8,
        "period_start_date": period_start,
    }
    pool._rows[(user_id, channel_b, "image_generation", date(2024, 6, 10))] = {
        "daily_count": 1,
        "monthly_count": 4,
        "period_start_date": period_start,
    }
    # Different operation type — should not be included
    pool._rows[(user_id, channel_a, "music_generation", date(2024, 6, 5))] = {
        "daily_count": 3,
        "monthly_count": 15,
        "period_start_date": period_start,
    }

    count = await repo.get_monthly_count(
        user_id, "image_generation", period_start
    )
    assert count == 12  # 8 + 4


@pytest.mark.asyncio
async def test_get_monthly_count_excludes_other_periods(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Only counts records matching the specific period_start_date."""
    user_id = uuid4()
    channel_id = uuid4()

    pool._rows[(user_id, channel_id, "music_generation", date(2024, 5, 15))] = {
        "daily_count": 2,
        "monthly_count": 10,
        "period_start_date": date(2024, 5, 1),
    }
    pool._rows[(user_id, channel_id, "music_generation", date(2024, 6, 15))] = {
        "daily_count": 1,
        "monthly_count": 3,
        "period_start_date": date(2024, 6, 1),
    }

    count = await repo.get_monthly_count(
        user_id, "music_generation", date(2024, 6, 1)
    )
    assert count == 3


# ---------------------------------------------------------------------------
# Tests — increment_usage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_increment_usage_creates_new_record(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Creates a new record with counts of 1 when no prior record exists."""
    user_id = uuid4()
    channel_id = uuid4()
    usage_date = date(2024, 6, 15)
    period_start = date(2024, 6, 1)

    await repo.increment_usage(
        user_id, channel_id, "music_generation", usage_date, period_start
    )

    key = (user_id, channel_id, "music_generation", usage_date)
    assert key in pool._rows
    assert pool._rows[key]["daily_count"] == 1
    assert pool._rows[key]["monthly_count"] == 1
    assert pool._rows[key]["period_start_date"] == period_start


@pytest.mark.asyncio
async def test_increment_usage_increments_existing_record(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Increments both daily_count and monthly_count on existing record."""
    user_id = uuid4()
    channel_id = uuid4()
    usage_date = date(2024, 6, 15)
    period_start = date(2024, 6, 1)

    key = (user_id, channel_id, "music_generation", usage_date)
    pool._rows[key] = {
        "daily_count": 3,
        "monthly_count": 15,
        "period_start_date": period_start,
    }

    await repo.increment_usage(
        user_id, channel_id, "music_generation", usage_date, period_start
    )

    assert pool._rows[key]["daily_count"] == 4
    assert pool._rows[key]["monthly_count"] == 16


@pytest.mark.asyncio
async def test_increment_usage_with_none_channel(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Handles NULL channel_profile_id for upsert operations."""
    user_id = uuid4()
    usage_date = date(2024, 6, 15)
    period_start = date(2024, 6, 1)

    await repo.increment_usage(
        user_id, None, "text_generation", usage_date, period_start
    )

    key = (user_id, None, "text_generation", usage_date)
    assert key in pool._rows
    assert pool._rows[key]["daily_count"] == 1
    assert pool._rows[key]["monthly_count"] == 1


@pytest.mark.asyncio
async def test_increment_usage_multiple_times(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Multiple increments accumulate correctly."""
    user_id = uuid4()
    channel_id = uuid4()
    usage_date = date(2024, 6, 15)
    period_start = date(2024, 6, 1)

    for _ in range(5):
        await repo.increment_usage(
            user_id, channel_id, "image_generation", usage_date, period_start
        )

    key = (user_id, channel_id, "image_generation", usage_date)
    assert pool._rows[key]["daily_count"] == 5
    assert pool._rows[key]["monthly_count"] == 5


@pytest.mark.asyncio
async def test_increment_usage_isolates_partitions(
    repo: UsageTrackingRepository,
    pool: FakeAsyncPGPool,
) -> None:
    """Incrementing one partition does not affect others."""
    user_id = uuid4()
    channel_a = uuid4()
    channel_b = uuid4()
    usage_date = date(2024, 6, 15)
    period_start = date(2024, 6, 1)

    await repo.increment_usage(
        user_id, channel_a, "music_generation", usage_date, period_start
    )
    await repo.increment_usage(
        user_id, channel_a, "music_generation", usage_date, period_start
    )
    await repo.increment_usage(
        user_id, channel_b, "music_generation", usage_date, period_start
    )

    key_a = (user_id, channel_a, "music_generation", usage_date)
    key_b = (user_id, channel_b, "music_generation", usage_date)
    assert pool._rows[key_a]["daily_count"] == 2
    assert pool._rows[key_b]["daily_count"] == 1
