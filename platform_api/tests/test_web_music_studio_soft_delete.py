"""S04 "Recently Deleted": deletion is soft, with recovery."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError
from platform_api.services.web_music_service import WebMusicService


def _service() -> WebMusicService:
    return WebMusicService(AsyncMock(), AsyncMock(), redis=None)


def _row(**overrides):
    row = {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "Deleted",
        "major_version": 2,
        "bpm": 120,
        "time_signature": "4/4",
        "data": {"tracks": [], "lanes": []},
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
async def test_delete_soft_deletes_instead_of_removing_the_row() -> None:
    service = _service()
    row = _row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_endpoint = lambda: None

    await service.delete_studio_project(row["user_id"], row["id"])

    sql = service._pool.fetchrow.await_args.args[0]
    assert "UPDATE studio_projects" in sql
    assert "deleted_at = now()" in sql
    assert "DELETE FROM" not in sql


@pytest.mark.asyncio
async def test_delete_rejects_a_project_that_is_already_gone() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.delete_studio_project(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_restore_clears_deleted_at_and_returns_a_list_item() -> None:
    service = _service()
    row = _row()
    service._pool.fetchrow = AsyncMock(return_value=row)

    result = await service.restore_studio_project(row["user_id"], row["id"])

    sql = service._pool.fetchrow.await_args.args[0]
    assert "deleted_at = NULL" in sql
    assert "deleted_at IS NOT NULL" in sql
    assert result["id"] == str(row["id"])
    assert "data" not in result


@pytest.mark.asyncio
async def test_restore_404s_when_the_project_is_not_deleted() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.restore_studio_project(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_list_filters_by_the_deleted_flag() -> None:
    service = _service()
    service._pool.fetch = AsyncMock(return_value=[])
    service._pool.fetchval = AsyncMock(return_value=0)
    service._studio_batch_sync_statuses = AsyncMock(return_value={})

    await service.list_studio_projects(uuid4(), deleted=True)

    sql = service._pool.fetch.await_args.args[0]
    assert "p.deleted_at IS NOT NULL" in sql
    assert service._pool.fetch.await_args.args[5] is True


def test_payload_carries_deleted_at_for_the_card_meta() -> None:
    row = _row()
    payload = WebMusicService._studio_project_payload(row, include_data=False)
    assert payload["deleted_at"] is None
