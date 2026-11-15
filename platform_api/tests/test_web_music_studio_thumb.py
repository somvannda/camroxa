"""S04: the project-card thumb travels with list rows and stays bounded."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.web_music_service import WebMusicService


def _service() -> WebMusicService:
    service = WebMusicService(AsyncMock(), AsyncMock(), redis=None)
    service._pool.fetch = AsyncMock(return_value=[])
    service._pool.fetchval = AsyncMock(return_value=0)
    service._studio_batch_sync_statuses = AsyncMock(return_value={})
    return service


def _row(data, **overrides):
    row = {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "Card",
        "major_version": 2,
        "bpm": 120,
        "time_signature": "4/4",
        "data": data,
        "created_at": None,
        "updated_at": None,
        "deleted_at": None,
        "pinned": False,
        "archived": False,
        "tags": [],
        "comment_count": 0,
        "last_comment_at": None,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_list_rows_carry_the_thumb_summary() -> None:
    service = _service()
    data = {
        "lanes": [
            {"id": "a", "start": 0, "duration": 4},
            {"id": "b", "start": 4, "duration": 2},
        ],
        "tracks": [{"color": "#ff0000", "clipIds": ["a", "b"]}],
    }
    row = _row(data)
    service._pool.fetch = AsyncMock(return_value=[row])
    service._pool.fetchval = AsyncMock(return_value=1)

    result = await service.list_studio_projects(row["user_id"])

    item = result["items"][0]
    assert item["thumb"] == {
        "tracks": [{"c": "#ff0000", "clips": [{"s": 0, "d": 4}, {"s": 4, "d": 2}]}],
        "end": 6,
    }
    # The card gets a summary, never the arrangement itself.
    assert "data" not in item


@pytest.mark.asyncio
async def test_list_thumb_is_bounded_for_a_large_project() -> None:
    service = _service()
    data = {
        "lanes": [
            {"id": f"c{index}", "start": index, "duration": 1} for index in range(40)
        ],
        "tracks": [
            {"color": "#123456", "clipIds": [f"c{index}" for index in range(40)]}
            for _ in range(20)
        ],
    }
    row = _row(data)
    service._pool.fetch = AsyncMock(return_value=[row])
    service._pool.fetchval = AsyncMock(return_value=1)

    result = await service.list_studio_projects(row["user_id"])

    thumb = result["items"][0]["thumb"]
    assert len(thumb["tracks"]) == 12
    assert all(len(track["clips"]) == 24 for track in thumb["tracks"])
    assert thumb["end"] == 24


@pytest.mark.asyncio
async def test_list_thumb_tolerates_a_project_without_a_document() -> None:
    service = _service()
    service._pool.fetch = AsyncMock(return_value=[_row(None)])
    service._pool.fetchval = AsyncMock(return_value=1)

    result = await service.list_studio_projects(uuid4())

    assert result["items"][0]["thumb"] == {"tracks": [], "end": 0}


@pytest.mark.asyncio
async def test_deleted_tab_rows_keep_the_thumb_and_deletion_time() -> None:
    service = _service()
    deleted_at = datetime(2026, 11, 14, 9, 30, tzinfo=timezone.utc)
    data = {
        "lanes": [{"id": "a", "start": 0, "duration": 8}],
        "tracks": [{"color": "#00ff00", "clipIds": ["a"]}],
    }
    row = _row(data, deleted_at=deleted_at)
    service._pool.fetch = AsyncMock(return_value=[row])
    service._pool.fetchval = AsyncMock(return_value=1)

    result = await service.list_studio_projects(row["user_id"], deleted=True)

    item = result["items"][0]
    assert item["deleted_at"] == deleted_at.isoformat()
    assert item["thumb"]["end"] == 8
    assert item["thumb"]["tracks"] == [{"c": "#00ff00", "clips": [{"s": 0, "d": 8}]}]
