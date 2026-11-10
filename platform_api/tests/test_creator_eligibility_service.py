"""Tests for earning eligibility and notifications."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.creator_eligibility_service import (
    ELIGIBLE_EVENT,
    HALFWAY_EVENT,
    CreatorEligibilityService,
)


def _track(user_id):
    return {
        "id": uuid4(),
        "user_id": user_id,
        "title": "Bassac Moon",
        "valid_streams": 0,
        "unique_listeners": 0,
    }


def _eligibility(track, status="not_eligible"):
    return {
        "track_id": track["id"],
        "creator_id": track["user_id"],
        "status": status,
        "valid_streams": track["valid_streams"],
        "unique_listeners": track["unique_listeners"],
        "threshold_streams": 500,
        "threshold_listeners": 50,
        "notified_half_at": None,
        "notified_eligible_at": None,
        "eligible_at": None,
        "earning_started_at": None,
        "updated_at": None,
    }


def _service():
    service = CreatorEligibilityService(AsyncMock())
    service._thresholds = AsyncMock(return_value=(500, 50))
    return service


@pytest.mark.asyncio
async def test_below_threshold_stays_not_eligible_without_notification() -> None:
    user_id = uuid4()
    track = _track(user_id)
    track["valid_streams"] = 10
    track["unique_listeners"] = 2
    service = _service()
    service._pool.fetchrow = AsyncMock(
        side_effect=[track, None, _eligibility(track, "not_eligible")]
    )
    service._pool.execute = AsyncMock()

    await service.refresh_track(track["id"])

    service._pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_halfway_queues_a_reminder() -> None:
    user_id = uuid4()
    track = _track(user_id)
    track["valid_streams"] = 260
    track["unique_listeners"] = 26
    service = _service()
    service._pool.fetchrow = AsyncMock(
        side_effect=[track, None, _eligibility(track, "not_eligible")]
    )
    service._pool.execute = AsyncMock()

    await service.refresh_track(track["id"])

    service._pool.execute.assert_awaited_once()
    assert HALFWAY_EVENT in service._pool.execute.await_args.args


@pytest.mark.asyncio
async def test_eligible_track_queues_the_earning_notification() -> None:
    user_id = uuid4()
    track = _track(user_id)
    track["valid_streams"] = 600
    track["unique_listeners"] = 60
    service = _service()
    service._pool.fetchrow = AsyncMock(
        side_effect=[track, None, _eligibility(track, "eligible")]
    )
    service._pool.execute = AsyncMock()

    await service.refresh_track(track["id"])

    service._pool.execute.assert_awaited_once()
    assert ELIGIBLE_EVENT in service._pool.execute.await_args.args


@pytest.mark.asyncio
async def test_list_creator_summarises_eligibility() -> None:
    user_id = uuid4()
    track = _track(user_id)
    rows = [
        {
            **_eligibility(track, "eligible"),
            "title": "Bassac Moon",
            "origin": "ai_assisted",
            "publish_status": "published",
        },
        {
            **_eligibility(track, "earning"),
            "title": "Golden Hour",
            "origin": "original",
            "publish_status": "published",
        },
    ]
    service = _service()
    service._pool.fetch = AsyncMock(return_value=rows)

    payload = await service.list_creator(user_id)

    assert payload["summary"]["tracks"] == 2
    assert payload["summary"]["eligible"] == 1
    assert payload["summary"]["earning"] == 1
    assert payload["items"][0]["title"] == "Bassac Moon"
