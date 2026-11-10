"""Tests for royalty allocation math."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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
