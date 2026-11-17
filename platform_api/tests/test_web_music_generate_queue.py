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
    # Packs-only: unsubscribed users pay per song, so they get the batch cap too.
    assert WEB_MUSIC_GENERATE_QUEUE_CAP_FREE == 20
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
            model="V6_MINI",
            prompt="",
        )


@pytest.mark.asyncio
async def test_unsubscribed_user_gets_the_batch_cap() -> None:
    """Packs-only: a Free-plan/pack user can batch, so the cap is not tiered."""
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=False)

    assert await service._queue_cap_for_user(uuid4()) == WEB_MUSIC_GENERATE_QUEUE_CAP_PAID


@pytest.mark.asyncio
async def test_unsubscribed_user_is_capped_at_20(mute_blocklist) -> None:
    user_id = uuid4()
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=False)
    service._active_generate_queue_count = AsyncMock(return_value=20)

    with pytest.raises(RateLimitedError, match="already have 20"):
        await service.generate(
            user_id,
            mode="advanced",
            lyrics="verse",
            style="pop",
            title="Hello Song",
            instrumental=False,
            model="V6_MINI",
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
        model="V6_MINI",
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
        model="V6_MINI",
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
async def test_advanced_generate_keeps_the_clients_lyrics(mute_blocklist) -> None:
    """Desktop Create drafts its own lyrics, then submits advanced mode.

    Simple mode (web) ships an empty ``lyrics_brief``; advanced mode must not,
    or the worker would replace the listener's drafted lyrics before submit.
    """
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
    service._with_queue_fields = AsyncMock(side_effect=lambda _uid, quota: dict(quota))

    payload = await service.generate(
        user_id,
        mode="advanced",
        lyrics="verse one\nchorus",
        style="pop",
        title="Hello Song",
        instrumental=False,
        model="V6_MINI",
        prompt="",
    )

    kwargs = service._enqueue_web_generate.await_args.kwargs
    assert kwargs["lyrics_brief"] is None
    assert kwargs["lyrics"] == "verse one\nchorus"
    assert kwargs["title"] == "Hello Song"
    assert payload["title"] == "Hello Song"
    generation.submit_suno.assert_not_awaited()


@pytest.mark.asyncio
async def test_lyrics_already_on_the_row_are_never_rewritten() -> None:
    """A retried job (or the desktop path) must not pay for lyrics twice."""
    user_id = uuid4()
    task_id = uuid4()
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": task_id,
            "title": "Hello Song",
            "lyrics": "verse one",  # already drafted client-side
            "style": "pop",
            "model": "V6_MINI",
            "instrumental": False,
            "external_task_id": None,
            "negative_tags": None,
            "status": "pending",
        }
    )
    service = WebMusicService(pool, MagicMock())
    service._write_simple_song = AsyncMock()

    await service.write_queued_lyrics(
        user_id, task_id, brief={"prompt": "a song"}, reservation_id="res-1"
    )

    service._write_simple_song.assert_not_awaited()


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
            "model": "V6_MINI",
            "instrumental": False,
            "external_task_id": None,
            "negative_tags": None,
            "vocal_gender": None,
            "style_weight": 0.5,
            "weirdness_constraint": 0.5,
            "audio_weight": 0.5,
            "reference_image_urls": "[]",
            "reference_video_urls": "[]",
            "persona_id": None,
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
    # The worker must pass the task id too: the recorded debit's ref_id may have
    # been relinked from the reservation id to the task id before the refund.
    kwargs = service._release_daily_slot.await_args.kwargs
    assert kwargs["reference_id"] == "res-1"
    assert kwargs["task_id"] == str(task_id)


@pytest.mark.asyncio
async def test_dead_generate_job_marks_the_task_failed(monkeypatch) -> None:
    """A generate job that exhausts its attempts must not leave the task pending.

    Run 1 of the W6 provider matrix found three rows stuck at `pending` with
    `error_message = NULL` because the job died (attempts exhausted) and nothing
    propagated to the task, so the user saw a spinner and the reservation was held.
    """
    from platform_api import worker

    captured: dict[str, object] = {}

    class FakeWebMusicService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def _fail_queued_generate(
            self, user_id, task_id, *, reservation_id: str, message: str
        ) -> None:
            captured.update(
                user_id=user_id,
                task_id=task_id,
                reservation_id=reservation_id,
                message=message,
            )

    monkeypatch.setattr(
        "platform_api.services.web_music_service.WebMusicService", FakeWebMusicService
    )
    monkeypatch.setattr("platform_api.dependencies.get_db_pool", lambda: object())
    monkeypatch.setattr("platform_api.dependencies.get_generation_service", lambda: object())
    monkeypatch.setattr("platform_api.dependencies.get_redis", lambda: None)

    user_id = uuid4()
    task_id = uuid4()
    job = MagicMock()
    job.id = "job-1"
    job.job_type = JOB_WEB_MUSIC_GENERATE
    job.user_id = str(user_id)
    job.payload = {
        "task_id": str(task_id),
        "user_id": str(user_id),
        "reservation_id": "res-1",
    }

    await worker._fail_dead_generate(job, "boom")

    assert captured["task_id"] == task_id
    assert captured["user_id"] == user_id
    assert captured["reservation_id"] == "res-1"
    assert "refunded" in str(captured["message"]).lower()


@pytest.mark.asyncio
async def test_dead_generate_ignores_other_job_types(monkeypatch) -> None:
    from platform_api import worker

    class ExplodingService:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("should not build the service for another job type")

    monkeypatch.setattr(
        "platform_api.services.web_music_service.WebMusicService", ExplodingService
    )

    job = MagicMock()
    job.job_type = "execute_batch"
    job.payload = {}
    await worker._fail_dead_generate(job, "boom")
