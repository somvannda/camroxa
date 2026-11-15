"""Retrying a failed Simple-mode song: new charge, same saved description."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.exceptions import (
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from platform_api.services.web_music_service import WebMusicService

_BRIEF = {
    "prompt": "High-energy Eurodance and Hands Up track",
    "theme": "a rooftop sunrise",
    "structure": "Chorus, Verse, Chorus",
    "title": "",
}


def _failed_row(task_id, **overrides):
    row = {
        "id": task_id,
        "status": "failed",
        "model": "V6",
        "title": "Untitled",
        "style": "Eurodance",
        "instrumental": False,
        "is_preview": False,
        "workspace_id": uuid4(),
        "kind": "music",
        "lyrics_brief": _BRIEF,
        "trashed": 0,
    }
    row.update(overrides)
    return row


def _service(row) -> WebMusicService:
    service = WebMusicService(AsyncMock(), MagicMock())
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._pool.fetchval = AsyncMock(return_value=row["id"] if row else None)
    service._pool.execute = AsyncMock()
    service._queue_cap_for_user = AsyncMock(return_value=20)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    service._reserve_daily_slot = AsyncMock(
        return_value={"limit": 1000, "used": 1, "remaining": 99, "is_pro": True}
    )
    service._release_daily_slot = AsyncMock()
    service._is_paid_queue_user = AsyncMock(return_value=True)
    service._link_generation_debit_reference = AsyncMock()
    service._with_queue_fields = AsyncMock(side_effect=lambda _uid, quota: dict(quota))
    return service


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    repo = MagicMock()
    repo.enqueue = AsyncMock()
    monkeypatch.setattr("platform_api.dependencies.get_job_queue_repo", lambda: repo)
    return repo


@pytest.mark.asyncio
async def test_retry_requeues_the_saved_brief_and_charges(queue: AsyncMock) -> None:
    task_id = uuid4()
    service = _service(_failed_row(task_id))

    payload = await service.retry_failed_generation(uuid4(), task_id)

    assert payload["status"] == "QUEUED"
    assert payload["task_id"] == str(task_id)
    service._reserve_daily_slot.assert_awaited()  # retry is a new charge
    job = queue.enqueue.await_args.kwargs
    assert job["payload"]["lyrics_brief"] == _BRIEF
    assert job["payload"]["task_id"] == str(task_id)
    # The row goes back to pending with the previous attempt's error cleared.
    reset = [
        call.args
        for call in service._pool.fetchval.await_args_list
        if "SET status = $3" in str(call.args[0])
    ]
    assert reset and reset[0][3] == "pending"


@pytest.mark.asyncio
async def test_retry_refuses_a_song_that_did_not_fail() -> None:
    task_id = uuid4()
    service = _service(_failed_row(task_id, status="success"))

    with pytest.raises(ValidationError, match="Only a failed song"):
        await service.retry_failed_generation(uuid4(), task_id)
    service._reserve_daily_slot.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_refuses_another_users_song() -> None:
    service = _service(None)  # the scoped query returns nothing

    with pytest.raises(NotFoundError):
        await service.retry_failed_generation(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_retry_refuses_a_song_without_a_saved_description() -> None:
    """Advanced-mode songs and sounds carry no brief; the form does."""
    task_id = uuid4()
    service = _service(_failed_row(task_id, lyrics_brief=None))

    with pytest.raises(ValidationError, match="no saved description"):
        await service.retry_failed_generation(uuid4(), task_id)
    service._reserve_daily_slot.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_respects_the_queue_cap() -> None:
    task_id = uuid4()
    service = _service(_failed_row(task_id))
    service._active_generate_queue_count = AsyncMock(return_value=20)

    with pytest.raises(RateLimitedError):
        await service.retry_failed_generation(uuid4(), task_id)
    service._reserve_daily_slot.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_refunds_when_the_row_was_already_claimed(queue: AsyncMock) -> None:
    """Two tabs clicking Retry: the loser must not keep the charge."""
    task_id = uuid4()
    service = _service(_failed_row(task_id))
    service._pool.fetchval = AsyncMock(return_value=None)  # UPDATE matched nothing

    with pytest.raises(ValidationError, match="already being retried"):
        await service.retry_failed_generation(uuid4(), task_id)

    service._release_daily_slot.assert_awaited()
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_refunds_when_the_queue_rejects_the_job(queue: AsyncMock) -> None:
    task_id = uuid4()
    service = _service(_failed_row(task_id))
    queue.enqueue = AsyncMock(side_effect=RuntimeError("redis down"))

    with pytest.raises(RuntimeError, match="redis down"):
        await service.retry_failed_generation(uuid4(), task_id)

    service._release_daily_slot.assert_awaited()
    # The row must not read as "queued" forever.
    restored = [
        call.args
        for call in service._pool.execute.await_args_list
        if "SET status = $3" in str(call.args[0])
    ]
    assert restored and restored[0][3] == "failed"
