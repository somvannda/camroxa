"""Tests for streaming upload scheduling."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.streaming_upload_service import StreamingUploadService


def test_schedule_suno_streaming_upload_creates_background_task(monkeypatch) -> None:
    created: list[asyncio.Task] = []

    def _capture_task(coro):
        task = asyncio.get_event_loop().create_task(coro)
        created.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", _capture_task)

    service = StreamingUploadService(AsyncMock())
    task_id = uuid4()
    service.schedule_suno_streaming_upload(suno_task_id=task_id)

    assert len(created) == 1
    created[0].cancel()


@pytest.mark.asyncio
async def test_upload_mp3_variant_skips_when_already_success() -> None:
    suno_task_id = uuid4()
    song_id = uuid4()
    batch_id = uuid4()
    user_id = uuid4()
    existing_job_id = uuid4()

    repo = AsyncMock()
    repo.get_latest_mp3_upload_job = AsyncMock(
        return_value={"id": existing_job_id, "status": "success"}
    )
    repo.create_upload_job = AsyncMock()
    repo.reset_upload_job_for_retry = AsyncMock()

    service = StreamingUploadService(AsyncMock())
    service._repo = repo

    await service._upload_mp3_variant(
        context={
            "user_id": user_id,
            "song_id": song_id,
            "batch_id": batch_id,
            "suno_task_id": suno_task_id,
            "ok_album": "Album",
            "song_title": "Track",
            "song_lyrics": "",
            "audio_url_ok": "https://cdn1.suno.ai/ok.mp3",
            "audio_url_alt": "",
        },
        variant="ok",
        source_url="https://cdn1.suno.ai/ok.mp3",
    )

    repo.create_upload_job.assert_not_called()
    repo.reset_upload_job_for_retry.assert_not_called()


@pytest.mark.asyncio
async def test_upload_mp3_variant_reuses_failed_job(monkeypatch) -> None:
    suno_task_id = uuid4()
    song_id = uuid4()
    batch_id = uuid4()
    user_id = uuid4()
    existing_job_id = uuid4()

    repo = AsyncMock()
    repo.get_latest_mp3_upload_job = AsyncMock(
        return_value={"id": existing_job_id, "status": "failed"}
    )
    repo.create_upload_job = AsyncMock()
    repo.reset_upload_job_for_retry = AsyncMock()
    repo.mark_upload_job = AsyncMock()

    monkeypatch.setattr(
        "platform_api.services.streaming_upload_service.resolve_streaming_storage_config",
        AsyncMock(return_value=SimpleNamespace(configured=False)),
    )

    service = StreamingUploadService(AsyncMock())
    service._repo = repo

    await service._upload_mp3_variant(
        context={
            "user_id": user_id,
            "song_id": song_id,
            "batch_id": batch_id,
            "suno_task_id": suno_task_id,
            "ok_album": "Album",
            "song_title": "Track",
            "song_lyrics": "",
            "audio_url_ok": "https://cdn1.suno.ai/ok.mp3",
            "audio_url_alt": "",
        },
        variant="ok",
        source_url="https://cdn1.suno.ai/ok.mp3",
    )

    repo.reset_upload_job_for_retry.assert_awaited_once()
    repo.create_upload_job.assert_not_called()
    repo.mark_upload_job.assert_awaited()
