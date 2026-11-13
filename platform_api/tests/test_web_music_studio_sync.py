"""Suno Studio mirror status/refresh proxies: ownership first, then the mirror."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError
from platform_api.services.web_music_service import WebMusicService


def _service() -> WebMusicService:
    return WebMusicService(AsyncMock(), AsyncMock(), redis=None)


PENDING = {
    "status": "pending",
    "suno_project_id": None,
    "suno_version_id": None,
    "last_error": None,
    "synced_at": None,
    "skipped_clips": [],
    "state_sync": False,
}


@pytest.mark.asyncio
async def test_status_returns_pending_without_a_link() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})
    service._studio_sync_request = AsyncMock(return_value=None)

    result = await service.studio_sync_status(uuid4(), uuid4())

    assert result == PENDING


@pytest.mark.asyncio
async def test_status_returns_the_mirror_view() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})
    mirrored = {**PENDING, "status": "linked", "suno_project_id": "suno-1"}
    service._studio_sync_request = AsyncMock(return_value=mirrored)

    result = await service.studio_sync_status(uuid4(), uuid4())

    assert result["status"] == "linked"
    assert result["suno_project_id"] == "suno-1"


@pytest.mark.asyncio
async def test_status_checks_ownership_before_calling_the_mirror() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)
    service._studio_sync_request = AsyncMock()

    with pytest.raises(NotFoundError):
        await service.studio_sync_status(uuid4(), uuid4())

    service._studio_sync_request.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_proxies_the_read_only_check() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})
    service._studio_sync_request = AsyncMock(return_value={**PENDING, "status": "conflict"})

    result = await service.refresh_studio_project(uuid4(), uuid4())

    assert result["status"] == "conflict"
    service._studio_sync_request.assert_awaited_once()
    assert service._studio_sync_request.await_args.args[2] == "refresh"


@pytest.mark.asyncio
async def test_force_sync_refuses_without_a_document() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.sync_studio_project(uuid4(), uuid4())
