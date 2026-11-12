"""Polled Studio presence: one row per editor session, lease-filtered on read."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError
from platform_api.services.web_music_service import WebMusicService


def _service() -> WebMusicService:
    return WebMusicService(AsyncMock(), AsyncMock(), redis=None)


@pytest.mark.asyncio
async def test_touch_presence_upserts_a_session_row() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})

    result = await service.touch_studio_presence(
        uuid4(),
        uuid4(),
        client_id="tab-1",
        display_name="Duke",
        color="#38bdf8",
        cursor_time=12.5,
        playhead=12.5,
    )

    assert result == {"ok": True}
    service._pool.execute.assert_awaited_once()
    query = service._pool.execute.await_args.args[0]
    assert "ON CONFLICT (project_id, client_id)" in query


@pytest.mark.asyncio
async def test_list_presence_returns_other_active_sessions() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})
    other = uuid4()
    service._pool.fetch = AsyncMock(
        return_value=[
            {
                "client_id": "tab-2",
                "user_id": other,
                "display_name": "Malis",
                "color": "#a78bfa",
                "cursor_time": 4.0,
                "playhead": 9.5,
                "updated_at": datetime(2026, 11, 12, 12, 0, tzinfo=UTC),
            }
        ]
    )

    result = await service.list_studio_presence(uuid4(), uuid4(), client_id="tab-1")

    assert result["items"] == [
        {
            "client_id": "tab-2",
            "user_id": str(other),
            "display_name": "Malis",
            "color": "#a78bfa",
            "cursor_time": 4.0,
            "playhead": 9.5,
            "updated_at": "2026-11-12T12:00:00+00:00",
        }
    ]


@pytest.mark.asyncio
async def test_presence_requires_an_owned_project() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.list_studio_presence(uuid4(), uuid4(), client_id="tab-1")
