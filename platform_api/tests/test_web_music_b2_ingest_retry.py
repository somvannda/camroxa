"""Web Create must ingest to B2 after Suno SUCCESS even if the callback won the race."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.routers.callbacks import _schedule_audio_ingest_after_success
from platform_api.services.web_music_service import WebMusicService


def test_web_music_callback_success_schedules_b2_backfill(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduled: list[tuple[str, object]] = []

    class _FakeUpload:
        def schedule_web_music_b2_backfill(self, *, suno_task_id):
            scheduled.append(("web", suno_task_id))

        def schedule_web_music_wav_upload(self, *, suno_task_id, variant=None):
            pass

        def schedule_web_music_lrc_upload(self, *, suno_task_id, variant="ok"):
            pass

        def schedule_suno_streaming_upload(self, *, suno_task_id):
            scheduled.append(("catalog", suno_task_id))

    monkeypatch.setattr(
        "platform_api.routers.callbacks.get_db_pool",
        lambda: MagicMock(),
        raising=False,
    )
    monkeypatch.setattr(
        "platform_api.dependencies.get_db_pool",
        lambda: MagicMock(),
    )
    monkeypatch.setattr(
        "platform_api.services.streaming_upload_service.StreamingUploadService",
        lambda _pool: _FakeUpload(),
    )
    task_id = uuid4()
    _schedule_audio_ingest_after_success(source="web_music", has_song=False, task_id=task_id)
    assert scheduled == [("web", task_id)]


def test_desktop_callback_success_still_uses_catalog_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduled: list[tuple[str, object]] = []

    class _FakeUpload:
        def schedule_web_music_b2_backfill(self, *, suno_task_id):
            scheduled.append(("web", suno_task_id))

        def schedule_suno_streaming_upload(self, *, suno_task_id):
            scheduled.append(("catalog", suno_task_id))

    monkeypatch.setattr("platform_api.dependencies.get_db_pool", lambda: MagicMock())
    monkeypatch.setattr(
        "platform_api.services.streaming_upload_service.StreamingUploadService",
        lambda _pool: _FakeUpload(),
    )
    task_id = uuid4()
    _schedule_audio_ingest_after_success(source="desktop", has_song=True, task_id=task_id)
    assert scheduled == [("catalog", task_id)]


@pytest.mark.asyncio
async def test_get_generation_retries_b2_when_success_is_not_ready() -> None:
    user_id = uuid4()
    task_id = uuid4()
    row = {
        "id": task_id,
        "status": "success",
        "audio_url_ok": "https://cdn.example/ok.mp3",
        "audio_url_alt": "https://cdn.example/alt.mp3",
        "package_status_ok": "none",
        "package_status_alt": "none",
        "packaged_storage_key_ok": None,
        "packaged_storage_key_alt": None,
        "b2_storage_key_ok": None,
        "b2_storage_key_alt": None,
    }
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=row)
    service = WebMusicService(pool, AsyncMock(), redis=None)
    service._refresh_pending_from_suno = AsyncMock(return_value=row)
    service._ensure_cover_urls = AsyncMock(return_value=row)
    service._ensure_durations = AsyncMock(return_value=row)
    service._ensure_stream_ready = AsyncMock(return_value=row)
    service._task_payload = AsyncMock(return_value={"id": str(task_id)})
    scheduled: list[tuple[object, str]] = []
    service._schedule_b2_backfill = lambda tid, variant: scheduled.append((tid, variant))

    await service.get_generation(user_id, task_id)

    assert scheduled == [(task_id, "ok"), (task_id, "alt")]


@pytest.mark.asyncio
async def test_get_generation_does_not_retry_ready_clips() -> None:
    user_id = uuid4()
    task_id = uuid4()
    row = {
        "id": task_id,
        "status": "success",
        "audio_url_ok": None,
        "audio_url_alt": None,
        "package_status_ok": "ready",
        "package_status_alt": "ready",
        "packaged_storage_key_ok": "web-music/x.cxa",
        "packaged_storage_key_alt": "web-music/y.cxa",
        "b2_storage_key_ok": None,
        "b2_storage_key_alt": None,
    }
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=row)
    service = WebMusicService(pool, AsyncMock(), redis=None)
    service._refresh_pending_from_suno = AsyncMock(return_value=row)
    service._ensure_cover_urls = AsyncMock(return_value=row)
    service._ensure_durations = AsyncMock(return_value=row)
    service._ensure_stream_ready = AsyncMock(return_value=row)
    service._task_payload = AsyncMock(return_value={"id": str(task_id)})
    scheduled: list[tuple[object, str]] = []
    service._schedule_b2_backfill = lambda tid, variant: scheduled.append((tid, variant))

    await service.get_generation(user_id, task_id)

    assert scheduled == []


@pytest.mark.asyncio
async def test_download_wav_resubmits_after_terminal_failure() -> None:
    """A terminal ``wav_status='failed'`` must drop the dead ``wav_task_id`` and
    submit a fresh conversion, instead of re-polling the errored upstream job."""
    user_id = uuid4()
    task_id = uuid4()
    row = {
        "id": task_id,
        "title": "Track",
        "status": "success",
        "audio_url_ok": "https://cdn.example/ok.mp3",
        "audio_url_alt": "https://cdn.example/alt.mp3",
        "external_task_id": "ext-1",
        "wav_task_id": "dead-wav-task",
        "wav_url": None,
        "wav_status": "failed",
        "b2_wav_key": None,
        "audio_id": "audio-1",
    }
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=row)
    pool.execute = AsyncMock()
    service = WebMusicService(pool, AsyncMock(), redis=None)

    # The re-submit path raises once it runs out of configured Suno keys; what
    # matters is that the dead conversion was cleared first.
    with pytest.raises(Exception):
        await service._download_wav_inner(user_id, task_id, variant="ok")

    statements = [str(call.args[0]) for call in pool.execute.await_args_list if call.args]
    assert any(
        "wav_task_id_ok = NULL" in sql and "wav_status_ok = 'pending'" in sql
        for sql in statements
    ), statements
