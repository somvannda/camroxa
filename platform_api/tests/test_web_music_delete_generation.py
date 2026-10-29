"""Trash semantics for web-music songs.

Deleting is a soft delete by default (``trashed_at``), so the song can be
restored from Trash. ``permanent=True`` keeps the old hard delete. In-flight
generations are still refused so active Suno jobs are not orphaned.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.models.products import SUNO_TASK_SOURCE_WEB_MUSIC
from platform_api.services.web_music_service import WebMusicService


def _service(pool: AsyncMock) -> WebMusicService:
    return WebMusicService(pool=pool, generation_service=AsyncMock(), redis=None)


@pytest.mark.asyncio
async def test_delete_moves_song_to_trash_by_default() -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={"id": task_id, "status": "FAILED", "trashed_at": None}
    )
    pool.execute = AsyncMock(return_value="UPDATE 1")

    await _service(pool).delete_generation(user_id, task_id)

    sql = pool.execute.await_args.args[0]
    assert "UPDATE suno_tasks" in sql
    assert "trashed_at = NOW()" in sql
    assert "DELETE FROM suno_tasks" not in sql
    assert pool.execute.await_args.args[1] == task_id
    assert pool.execute.await_args.args[2] == user_id
    assert pool.execute.await_args.args[3] == SUNO_TASK_SOURCE_WEB_MUSIC


@pytest.mark.asyncio
async def test_delete_is_idempotent_for_already_trashed_song() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={"id": uuid4(), "status": "SUCCESS", "trashed_at": "2026-10-29"}
    )
    pool.execute = AsyncMock()

    await _service(pool).delete_generation(uuid4(), uuid4())

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_permanent_delete_removes_row() -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={"id": task_id, "status": "FAILED", "trashed_at": None}
    )
    pool.execute = AsyncMock(return_value="DELETE 1")

    await _service(pool).delete_generation(user_id, task_id, permanent=True)

    sql = pool.execute.await_args.args[0]
    assert "DELETE FROM suno_tasks" in sql


@pytest.mark.asyncio
async def test_delete_missing_generation_raises_not_found() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()

    with pytest.raises(NotFoundError):
        await _service(pool).delete_generation(uuid4(), uuid4())

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PENDING", "running", "queued", ""])
async def test_delete_pending_generation_is_refused(status: str) -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={"id": task_id, "status": status, "trashed_at": None}
    )
    pool.execute = AsyncMock()

    with pytest.raises(ValidationError):
        await _service(pool).delete_generation(user_id, task_id)

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_clears_trashed_at() -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": task_id})
    pool.execute = AsyncMock(return_value="UPDATE 1")

    await _service(pool).restore_generation(user_id, task_id)

    sql = pool.execute.await_args.args[0]
    assert "trashed_at = NULL" in sql
    assert pool.execute.await_args.args[1] == task_id


@pytest.mark.asyncio
async def test_restore_missing_song_raises_not_found() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()

    with pytest.raises(NotFoundError):
        await _service(pool).restore_generation(uuid4(), uuid4())

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_trash_returns_deleted_count() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[{"id": uuid4()}, {"id": uuid4()}])

    deleted = await _service(pool).empty_trash(uuid4())

    assert deleted == 2
    sql = pool.fetch.await_args.args[0]
    assert "trashed_at IS NOT NULL" in sql
