"""Tests for royalty allocation math."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import DuplicateError, ValidationError
from platform_api.services.royalty_engine_service import (
    RoyaltyEngineService,
    allocate_royalties,
)


def _policy(cap_pct: int = 40):
    return {
        "pool": {"amount_usd": 3000},
        "reserve_pct": 10,
        "eligibility_streams": 500,
        "eligibility_unique_listeners": 50,
        "weights": {"original": 1.0, "ai_assisted": 0.6, "ai_generated": 0.3},
        "caps": {"per_track_weighted_streams": 500_000, "per_creator_pool_pct": cap_pct},
    }


def _row(creator_id, valid, unique, origin="original"):
    return {
        "creator_id": creator_id,
        "track_id": uuid4(),
        "origin": origin,
        "valid_streams": valid,
        "unique_listeners": unique,
    }


def test_weights_reserve_and_eligibility() -> None:
    creator_a = uuid4()
    creator_b = uuid4()
    creator_c = uuid4()
    result = allocate_royalties(
        [
            _row(creator_a, 1000, 100, "original"),
            _row(creator_b, 2000, 200, "ai_generated"),
            _row(creator_c, 400, 40, "original"),  # below threshold
        ],
        _policy(cap_pct=100),
    )

    assert result["pool_micros"] == 3_000_000_000
    assert result["reserve_micros"] == 300_000_000
    assert result["total_weighted_streams"] == 1600
    assert str(creator_c) not in result["creator_totals"]
    assert result["creator_totals"][str(creator_a)] == 1_687_500_000
    assert result["creator_totals"][str(creator_b)] == 1_012_500_000
    assert sum(result["creator_totals"].values()) == 2_700_000_000


def test_per_track_cap_limits_weighted_streams() -> None:
    creator = uuid4()
    result = allocate_royalties(
        [_row(creator, 2_000_000, 2_000, "ai_generated")],
        _policy(),
    )
    assert result["allocations"][0]["weighted_streams"] == 500_000


def test_per_creator_cap_limits_payout() -> None:
    creator = uuid4()
    result = allocate_royalties(
        [_row(creator, 5_000_000, 5_000, "original")],
        _policy(),
    )
    # 40% of the $3,000 pool = $1,200.
    assert result["creator_totals"][str(creator)] == 1_200_000_000


def test_no_eligible_tracks_returns_empty_allocation() -> None:
    result = allocate_royalties([_row(uuid4(), 10, 1, "original")], _policy())
    assert result["allocations"] == []
    assert result["creator_totals"] == {}
    assert result["total_weighted_streams"] == 0


@pytest.mark.asyncio
async def test_lock_period_marks_it_locked() -> None:
    period_id = uuid4()
    service = RoyaltyEngineService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        side_effect=[
            {"id": period_id, "status": "calculated"},
            {"id": period_id, "status": "locked"},
        ]
    )
    result = await service.lock_period(str(period_id))
    assert result["period"]["status"] == "locked"

class _FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, sql: str, *args):
        self.calls.append((sql, args))
        return "OK"

    async def __aenter__(self):
        return self

    def transaction(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, conn, *, period, reserve=0, already=None, accruals=None) -> None:
        self._conn = conn
        self._period = period
        self._reserve = reserve
        self._already = already
        self._accruals = accruals or []

    async def fetchrow(self, sql, *args):
        return self._period

    async def fetchval(self, sql, *args):
        if "Reserve release" in sql:
            return self._already
        return self._reserve

    async def fetch(self, sql, *args):
        return self._accruals

    def acquire(self):
        return self._conn


def _period(period_end, policy_id=None):
    from datetime import date
    return {
        "id": uuid4(),
        "period_start": date(2026, 1, 1),
        "period_end": period_end,
        "policy_id": policy_id,
    }


@pytest.mark.asyncio
async def test_release_reserve_is_blocked_inside_the_dispute_window() -> None:
    from datetime import date
    service = RoyaltyEngineService(_FakePool(_FakeConn(), period=_period(date.today())))
    with pytest.raises(ValidationError) as exc:
        await service.release_reserve(str(uuid4()))
    assert "hold_until" in (exc.value.details or {})


@pytest.mark.asyncio
async def test_release_reserve_rejects_a_second_release() -> None:
    from datetime import date
    service = RoyaltyEngineService(
        _FakePool(_FakeConn(), period=_period(date(2020, 1, 31)), reserve=5_000_000, already=1)
    )
    with pytest.raises(DuplicateError):
        await service.release_reserve(str(uuid4()))


@pytest.mark.asyncio
async def test_release_reserve_splits_pro_rata_and_nets_to_zero() -> None:
    from datetime import date
    a, b = uuid4(), uuid4()
    conn = _FakeConn()
    service = RoyaltyEngineService(
        _FakePool(
            conn,
            period=_period(date(2020, 1, 31)),
            reserve=1_000_001,
            accruals=[
                {"creator_id": a, "amount_micros": 60_000_000},
                {"creator_id": b, "amount_micros": 40_000_000},
            ],
        )
    )

    result = await service.release_reserve(str(uuid4()))

    assert result["released_micros"] == 1_000_001
    assert result["creators"] == 2
    earnings = [args for sql, args in conn.calls if "creator_earnings" in sql]
    assert len(earnings) == 2
    assert sum(args[3] for args in earnings) == 1_000_001



@pytest.mark.asyncio
async def test_release_due_reserves_skips_periods_it_cannot_release() -> None:
    service = RoyaltyEngineService(AsyncMock())
    service._pool.fetch = AsyncMock(return_value=[{"id": uuid4()}, {"id": uuid4()}])
    service.release_reserve = AsyncMock(
        side_effect=[{"released_micros": 1}, ValidationError("too early")]
    )

    released = await service.release_due_reserves()

    assert released == 1
    assert service.release_reserve.await_count == 2


@pytest.mark.asyncio
async def test_release_reserve_uses_a_permitted_ledger_entry_type() -> None:
    """The ledger check constraint allows 'release', not a made-up type."""
    from datetime import date

    a, b = uuid4(), uuid4()
    conn = _FakeConn()
    service = RoyaltyEngineService(
        _FakePool(
            conn,
            period=_period(date(2020, 1, 31)),
            reserve=1_000_000,
            accruals=[
                {"creator_id": a, "amount_micros": 50_000_000},
                {"creator_id": b, "amount_micros": 50_000_000},
            ],
        )
    )

    await service.release_reserve(str(uuid4()))

    ledger = [sql for sql, _ in conn.calls if "royalty_ledger" in sql]
    assert ledger, "expected ledger writes"
    assert all("'release'" in sql for sql in ledger)
    assert not any("reserve_release" in sql for sql in ledger)
