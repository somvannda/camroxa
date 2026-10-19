"""Delete a web-music song from the user's workspace.

Failed songs are already refunded, so deletion never touches the wallet; it only
removes the ``suno_tasks`` row (dependent playlist items / likes / play counts
cascade). In-flight generations are refused so active Suno jobs are not orphaned.
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
async def test_delete_failed_generation_removes_owned_row() -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": task_id, "status": "FAILED"})
    pool.execute = AsyncMock(return_value="DELETE 1")

    await _service(pool).delete_generation(user_id, task_id)

    sql = pool.execute.await_args.args[0]
    assert "DELETE FROM suno_tasks" in sql
    assert pool.execute.await_args.args[1] == task_id
    assert pool.execute.await_args.args[2] == user_id
    assert pool.execute.await_args.args[3] == SUNO_TASK_SOURCE_WEB_MUSIC


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
    pool.fetchrow = AsyncMock(return_value={"id": task_id, "status": status})
    pool.execute = AsyncMock()

    with pytest.raises(ValidationError):
        await _service(pool).delete_generation(user_id, task_id)

    pool.execute.assert_not_awaited()
