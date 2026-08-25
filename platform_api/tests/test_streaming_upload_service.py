"""Tests for streaming upload scheduling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from platform_api.services.streaming_upload_service import StreamingUploadService


def test_schedule_suno_streaming_upload_creates_background_task(monkeypatch) -> None:
    created: list[object] = []

    def _capture_task(coro):
        created.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr("asyncio.create_task", _capture_task)

    service = StreamingUploadService(AsyncMock())
    service.schedule_suno_streaming_upload(suno_task_id=uuid4())

    assert len(created) == 1


def test_web_music_b2_backfill_skips_while_inflight_or_cooling_down(monkeypatch) -> None:
    created: list[object] = []

    def _capture_task(coro):
        created.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr("asyncio.create_task", _capture_task)
    service = StreamingUploadService(AsyncMock())
    task_id = uuid4()

    service.schedule_web_music_b2_backfill(suno_task_id=task_id, variant="ok")
    service.schedule_web_music_b2_backfill(suno_task_id=task_id, variant="ok")
    assert len(created) == 1

    service._web_music_backfill_inflight.clear()
    service.schedule_web_music_b2_backfill(suno_task_id=task_id, variant="ok")
    assert len(created) == 1
