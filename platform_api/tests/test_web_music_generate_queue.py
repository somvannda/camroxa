"""Paid-first web Create queue: caps, enqueue, fulfill refund."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.exceptions import RateLimitedError
from platform_api.services.job_types import (
    JOB_WEB_MUSIC_GENERATE,
    PRI_SUNO_SUBMIT,
    PRI_WEB_MUSIC_FREE,
    PRI_WEB_MUSIC_PAID,
    WEB_MUSIC_GENERATE_QUEUE_CAP_FREE,
    WEB_MUSIC_GENERATE_QUEUE_CAP_PAID,
    resolve_worker_job_types,
)
from platform_api.services.web_music_service import WebMusicService


@pytest.fixture
def mute_blocklist(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MagicMock()
    service.get_runtime_config = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "platform_api.dependencies.get_suno_blocklist_service",
        lambda: service,
    )


def test_desktop_suno_still_outranks_web_paid() -> None:
    assert PRI_SUNO_SUBMIT > PRI_WEB_MUSIC_PAID > PRI_WEB_MUSIC_FREE
    assert WEB_MUSIC_GENERATE_QUEUE_CAP_PAID == 20
    assert WEB_MUSIC_GENERATE_QUEUE_CAP_FREE == 2
    assert JOB_WEB_MUSIC_GENERATE in resolve_worker_job_types("suno")


@pytest.mark.asyncio
async def test_paid_user_is_capped_at_20(mute_blocklist) -> None:
    user_id = uuid4()
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=True)
    service._active_generate_queue_count = AsyncMock(return_value=20)

    with pytest.raises(RateLimitedError, match="already have 20"):
        await service.generate(
            user_id,
            mode="advanced",
            lyrics="verse",
            style="pop",
            title="Hello Song",
            instrumental=False,
            model="V5_5",
            prompt="",
        )


@pytest.mark.asyncio
async def test_free_user_is_capped_at_2(mute_blocklist) -> None:
    user_id = uuid4()
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=False)
    service._active_generate_queue_count = AsyncMock(return_value=2)

    with pytest.raises(RateLimitedError, match="already have 2"):
        await service.generate(
            user_id,
            mode="advanced",
            lyrics="verse",
            style="pop",
            title="Hello Song",
            instrumental=False,
            model="V5_5",
            prompt="",
        )


@pytest.mark.asyncio
async def test_generate_enqueues_instead_of_calling_suno(mute_blocklist) -> None:
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.submit_suno = AsyncMock()
    service = WebMusicService(MagicMock(), generation)
    service._is_paid_queue_user = AsyncMock(return_value=True)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    service._reserve_daily_slot = AsyncMock(return_value={"limit": 1000, "used": 0, "remaining": 100, "is_pro": True})
    service._enqueue_web_generate = AsyncMock(return_value=task_id)
    service._link_generation_debit_reference = AsyncMock()
    service._resolve_workspace_id = AsyncMock(return_value=uuid4())
    service._with_queue_fields = AsyncMock(side_effect=lambda _uid, quota: {**quota, "queue_limit": 20, "queue_used": 1})

    payload = await service.generate(
        user_id,
        mode="advanced",
        lyrics="verse",
        style="pop",
        title="Hello Song",
        instrumental=False,
        model="V5_5",
        prompt="",
    )

    assert payload["status"] == "QUEUED"
    assert payload["task_id"] == str(task_id)
    generation.submit_suno.assert_not_awaited()
    service._enqueue_web_generate.assert_awaited()


@pytest.mark.asyncio
async def test_enqueue_paid_outranks_free(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    repo.enqueue = AsyncMock()
    monkeypatch.setattr("platform_api.dependencies.get_job_queue_repo", lambda: repo)
    service = WebMusicService(MagicMock(), MagicMock())
    service._pool.execute = AsyncMock()
    service._resolve_workspace_id = AsyncMock(return_value=uuid4())

    kwargs = dict(
        reservation_id="res-1",
        model="V5_5",
        title="Hello Song",
        lyrics="verse",
        style="pop",
        instrumental=False,
        negative_tags=None,
        vocal_gender=None,
        style_weight=0.5,
        weirdness_constraint=0.5,
        audio_weight=0.5,
        workspace_id=None,
    )
    service._is_paid_queue_user = AsyncMock(return_value=True)
    await service._enqueue_web_generate(uuid4(), **kwargs)
    assert repo.enqueue.await_args.kwargs["priority"] == PRI_WEB_MUSIC_PAID
    assert repo.enqueue.await_args.kwargs["job_type"] == JOB_WEB_MUSIC_GENERATE

    service._is_paid_queue_user = AsyncMock(return_value=False)
    await service._enqueue_web_generate(uuid4(), **kwargs)
    assert repo.enqueue.await_args.kwargs["priority"] == PRI_WEB_MUSIC_FREE


@pytest.mark.asyncio
async def test_fulfill_refunds_when_suno_rejects() -> None:
    user_id = uuid4()
    task_id = uuid4()
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": task_id,
            "title": "Hello Song",
            "lyrics": "verse",
            "style": "pop",
            "model": "V5_5",
            "instrumental": False,
            "external_task_id": None,
            "negative_tags": None,
            "vocal_gender": None,
            "style_weight": 0.5,
            "weirdness_constraint": 0.5,
            "audio_weight": 0.5,
        }
    )
    pool.execute = AsyncMock()
    generation = MagicMock()
    generation.submit_suno_external_id = AsyncMock(side_effect=RuntimeError("suno down"))
    service = WebMusicService(pool, generation)
    service._release_daily_slot = AsyncMock()

    with pytest.raises(RuntimeError, match="suno down"):
        await service.fulfill_queued_generate(user_id, task_id, reservation_id="res-1")

    service._release_daily_slot.assert_awaited()
