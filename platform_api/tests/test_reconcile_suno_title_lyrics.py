"""The pending-Suno reconciler must persist Suno's title and lyrics.

A provider webhook can be missed (unreachable callback URL, IP/HMAC guard,
transient network). The reconciler then polls a SUCCESS record that already
carries the title and lyrics; before this test it only copied status and audio
URLs, so a description-mode song stayed without a title forever.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import platform_api.dependencies as deps
import platform_api.services.suno_audio_resolver as resolver
from platform_api.clients.suno_client import SunoGeneratePollResult
from platform_api.models.enums import TaskStatus
from platform_api.tests.test_batch_service import make_service


def _row() -> dict:
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "song_id": uuid4(),
        "batch_id": uuid4(),
        "external_task_id": "ext-1",
        "status": "pending",
        "audio_url_ok": None,
        "audio_url_alt": None,
        "audio_id_ok": None,
        "audio_id_alt": None,
        "created_at": datetime.now(timezone.utc),
    }


def _service():
    return make_service(
        AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    )


@pytest.mark.asyncio
async def test_reconcile_persists_suno_title_and_lyrics(monkeypatch):
    service = _service()
    row = _row()
    service._batch_repo.list_stuck_suno_pending_songs = AsyncMock(return_value=[])
    service._batch_repo.list_reconcilable_suno_tasks = AsyncMock(return_value=[row])
    service._batch_repo.update_status = AsyncMock()
    service._batch_repo.update_suno_generated_metadata = AsyncMock()
    service._batch_repo.get_batch_by_id = AsyncMock(return_value=None)
    service.handle_suno_task_update = AsyncMock()

    monkeypatch.setattr(deps, "get_db_pool", lambda: object())

    async def _poll(_pool, _ext):
        return SunoGeneratePollResult(
            state="success",
            audio_url_ok="https://cdn.example/a.mp3",
            audio_url_alt="https://cdn.example/b.mp3",
            title_ok="Pulse Tonight",
            title_alt="Pulse Tonight",
            lyrics="[Verse]\nmove, move, move",
        )

    monkeypatch.setattr(resolver, "poll_suno_generate_with_pool", _poll)

    reconciled = await service.reconcile_pending_suno_tasks(user_id=str(uuid4()), limit=25)

    assert reconciled == 1
    service._batch_repo.update_status.assert_awaited_once()
    assert service._batch_repo.update_status.await_args.kwargs["status"] == TaskStatus.SUCCESS
    service._batch_repo.update_suno_generated_metadata.assert_awaited_once()
    kwargs = service._batch_repo.update_suno_generated_metadata.await_args.kwargs
    assert kwargs["title_ok"] == "Pulse Tonight"
    assert kwargs["title_alt"] == "Pulse Tonight"
    assert "move, move, move" in kwargs["lyrics"]
    # The completion handler runs after the title/lyrics are on the task, so it
    # can copy them onto the song.
    service.handle_suno_task_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_skips_metadata_write_without_title_or_lyrics(monkeypatch):
    service = _service()
    row = _row()
    service._batch_repo.list_stuck_suno_pending_songs = AsyncMock(return_value=[])
    service._batch_repo.list_reconcilable_suno_tasks = AsyncMock(return_value=[row])
    service._batch_repo.update_status = AsyncMock()
    service._batch_repo.update_suno_generated_metadata = AsyncMock()
    service._batch_repo.get_batch_by_id = AsyncMock(return_value=None)
    service.handle_suno_task_update = AsyncMock()

    monkeypatch.setattr(deps, "get_db_pool", lambda: object())

    async def _poll(_pool, _ext):
        return SunoGeneratePollResult(
            state="success",
            audio_url_ok="https://cdn.example/a.mp3",
        )

    monkeypatch.setattr(resolver, "poll_suno_generate_with_pool", _poll)

    await service.reconcile_pending_suno_tasks(user_id=str(uuid4()), limit=25)

    service._batch_repo.update_suno_generated_metadata.assert_not_awaited()
    service.handle_suno_task_update.assert_awaited_once()
