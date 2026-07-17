"""Tests for streaming upload scheduling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

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
