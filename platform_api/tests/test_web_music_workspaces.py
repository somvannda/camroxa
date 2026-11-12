"""Workspace listing: names plus the per-workspace song count the library shows."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from platform_api.services.web_music_service import WebMusicService

USER_ID = uuid4()


class RecordingPool:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.sql = ""
        self.args: tuple = ()

    async def fetch(self, sql: str, *args: object) -> list[dict]:
        self.sql = sql
        self.args = args
        return self.rows


def _service(rows: list[dict]) -> tuple[WebMusicService, RecordingPool]:
    pool = RecordingPool(rows)
    service = WebMusicService(pool, AsyncMock())  # type: ignore[arg-type]
    service.ensure_default_workspace = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return service, pool


@pytest.mark.asyncio
async def test_list_workspaces_includes_song_counts() -> None:
    now = datetime(2026, 11, 5, tzinfo=timezone.utc)
    service, pool = _service(
        [
            {"id": uuid4(), "name": "My Workspace", "is_default": True, "created_at": now, "song_count": 946},
            {"id": uuid4(), "name": "Empty", "is_default": False, "created_at": now, "song_count": 0},
        ]
    )

    items = await service.list_workspaces(USER_ID)

    assert [item["name"] for item in items] == ["My Workspace", "Empty"]
    assert [item["song_count"] for item in items] == [946, 0]
    assert items[0]["is_default"] is True
    assert items[0]["created_at"] == now.isoformat()


@pytest.mark.asyncio
async def test_list_workspaces_counts_only_this_users_web_songs() -> None:
    service, pool = _service([])

    await service.list_workspaces(USER_ID)

    # The count is scoped to the user and to the web_music source, so desktop/MCP
    # rows cannot inflate a workspace's library badge.
    assert pool.args[0] == USER_ID
    assert pool.args[1] == "web_music"
    assert "GROUP BY workspace_id" in pool.sql
    assert "LEFT JOIN" in pool.sql


@pytest.mark.asyncio
async def test_missing_count_is_zero_not_null() -> None:
    """A row without the joined column still yields an int, not None."""
    service, _pool = _service([{"id": uuid4(), "name": "Legacy", "is_default": False, "created_at": None}])

    items = await service.list_workspaces(USER_ID)

    assert items[0]["song_count"] == 0
    assert items[0]["created_at"] is None
