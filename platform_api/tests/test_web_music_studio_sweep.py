"""Studio-operation sweeper.

A cover started from the feed only advanced while a client polled it, so the
startup sweeper polls abandoned operations, and a completed operation without a
feed row materializes one instead of dropping the audio.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.web_music_service import WebMusicService


def _service(pool: AsyncMock) -> WebMusicService:
    return WebMusicService(pool=pool, generation_service=AsyncMock(), redis=None)


@pytest.mark.asyncio
async def test_sweep_polls_each_unfinished_operation() -> None:
    user_id = uuid4()
    first, second = uuid4(), uuid4()
    pool = AsyncMock()
    pool.fetch = AsyncMock(
        return_value=[{"id": first, "user_id": user_id}, {"id": second, "user_id": user_id}]
    )

    service = _service(pool)
    service.get_studio_operation = AsyncMock(return_value={"id": str(first)})

    swept = await service.sweep_studio_operations(older_than_seconds=20, limit=5)

    assert swept == 2
    assert service.get_studio_operation.await_count == 2
    sql, older, limit, max_age = pool.fetch.await_args.args
    assert "studio_operations" in sql
    assert "make_interval(secs => $1)" in sql
    assert "make_interval(secs => $3)" in sql
    assert (older, limit, max_age) == (20, 5, 21600)


@pytest.mark.asyncio
async def test_sweep_keeps_going_when_one_poll_fails() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(
        return_value=[{"id": uuid4(), "user_id": uuid4()}, {"id": uuid4(), "user_id": uuid4()}]
    )
    service = _service(pool)
    service.get_studio_operation = AsyncMock(side_effect=[RuntimeError("boom"), {"id": "ok"}])

    swept = await service.sweep_studio_operations()

    assert swept == 1
    assert service.get_studio_operation.await_count == 2


@pytest.mark.asyncio
async def test_completed_operation_without_row_backfills_it() -> None:
    user_id = uuid4()
    operation_id = uuid4()
    source_id = uuid4()
    new_row_id = uuid4()

    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        side_effect=[
            None,  # the UPDATE finds no feed row for this operation
            {  # _materialize_studio_operation_song reads the source song
                "title": "Source",
                "lyrics": "[Instrumental]",
                "style": "ambient",
                "model": "chirp-v5",
                "instrumental": True,
                "workspace_id": None,
                "image_url_ok": None,
                "persona_id": None,
                "negative_tags": None,
                "vocal_gender": None,
            },
            {"id": new_row_id},  # the retried UPDATE now finds the row
        ]
    )
    pool.execute = AsyncMock(return_value="INSERT 1")

    service = _service(pool)

    class _Uploads:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def schedule_web_music_b2_backfill(self, **kwargs) -> None:
            self.calls.append(kwargs)

    uploads = _Uploads()
    service._upload_service = uploads

    await service._sync_studio_operation_song(
        user_id,
        {"id": operation_id, "task_id": source_id, "operation_type": "cover"},
        status="complete",
        result={
            "clips": [
                {
                    "id": "clip-1",
                    "title": "Covered",
                    "audioUrl": "https://example.com/a.mp3",
                    "metadata": {"duration": 180.5},
                }
            ]
        },
        error=None,
    )

    assert pool.fetchrow.await_count == 3
    assert pool.execute.await_count == 1
    insert_sql, *insert_args = pool.execute.await_args.args
    assert "INSERT INTO suno_tasks" in insert_sql
    assert f"studio:{operation_id}" in insert_args
    assert uploads.calls == [{"suno_task_id": new_row_id, "variant": "ok"}]
