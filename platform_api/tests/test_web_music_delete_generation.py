"""Trash semantics for web-music songs (per version).

Deleting is a soft delete by default and targets a single version (`ok` =
Version 1, `alt` = Version 2) or both. Stored in `trashed_variants`.
`permanent=True` keeps the old hard delete. In-flight generations are refused.
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
@pytest.mark.parametrize(
    ("variant", "expected"),
    [(None, ["ok", "alt"]), ("ok", ["ok"]), ("alt", ["alt"])],
)
async def test_delete_moves_selected_version_to_trash(
    variant: str | None, expected: list[str]
) -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": task_id, "status": "FAILED"})
    pool.execute = AsyncMock(return_value="UPDATE 1")

    await _service(pool).delete_generation(user_id, task_id, variant=variant)

    sql = pool.execute.await_args.args[0]
    assert "UPDATE suno_tasks" in sql
    assert "trashed_variants" in sql
    assert "DELETE FROM suno_tasks" not in sql
    assert pool.execute.await_args.args[1] == task_id
    assert pool.execute.await_args.args[2] == user_id
    assert pool.execute.await_args.args[3] == SUNO_TASK_SOURCE_WEB_MUSIC
    assert pool.execute.await_args.args[4] == expected


@pytest.mark.asyncio
async def test_delete_rejects_unknown_variant() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock()

    with pytest.raises(ValidationError):
        await _service(pool).delete_generation(uuid4(), uuid4(), variant="both")

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_permanent_delete_removes_row() -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": task_id, "status": "FAILED"})
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
    pool.fetchrow = AsyncMock(return_value={"id": task_id, "status": status})
    pool.execute = AsyncMock()

    with pytest.raises(ValidationError):
        await _service(pool).delete_generation(user_id, task_id)

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "expected"), [(None, ["ok", "alt"]), ("ok", ["ok"])]
)
async def test_restore_removes_versions_from_trash(
    variant: str | None, expected: list[str]
) -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": task_id})
    pool.execute = AsyncMock(return_value="UPDATE 1")

    await _service(pool).restore_generation(user_id, task_id, variant=variant)

    sql = pool.execute.await_args.args[0]
    assert "trashed_variants" in sql
    assert "NOT (v = ANY" in sql
    assert pool.execute.await_args.args[1] == task_id
    assert pool.execute.await_args.args[4] == expected


@pytest.mark.asyncio
async def test_restore_missing_song_raises_not_found() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()

    with pytest.raises(NotFoundError):
        await _service(pool).restore_generation(uuid4(), uuid4())

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_trash_deletes_fully_trashed_songs() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[{"id": uuid4()}, {"id": uuid4()}])

    deleted = await _service(pool).empty_trash(uuid4())

    assert deleted == 2
    sql = pool.fetch.await_args.args[0]
    assert "cardinality(trashed_variants) >= 2" in sql

@pytest.mark.asyncio
async def test_set_trash_batches_clip_ids() -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    task_a = uuid4()
    task_b = uuid4()

    updated = await _service(pool).set_trash(
        uuid4(),
        [f"{task_a}:ok", f"{task_b}:alt", "not-a-clip", f"{task_a}:both"],
        trashed=True,
    )

    assert updated == 2
    assert pool.execute.await_count == 2
    first = pool.execute.await_args_list[0].args
    assert first[1] == task_a
    assert first[4] == "ok"
    second = pool.execute.await_args_list[1].args
    assert second[1] == task_b
    assert second[4] == "alt"
