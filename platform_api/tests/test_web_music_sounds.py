"""Web Create Sounds: validation, queue cap, enqueue kind, submit branch."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.exceptions import RateLimitedError, ValidationError
from platform_api.services.job_types import (
    WEB_MUSIC_GENERATE_QUEUE_CAP_PAID,
)
from platform_api.services.web_music_service import WebMusicService

QUOTA = {"limit": 20, "used": 0, "remaining": 20, "is_pro": False}


@pytest.fixture
def mute_blocklist(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MagicMock()
    service.get_runtime_config = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "platform_api.dependencies.get_suno_blocklist_service",
        lambda: service,
    )


@pytest.mark.asyncio
async def test_sounds_rejects_a_short_prompt() -> None:
    service = WebMusicService(MagicMock(), MagicMock())
    with pytest.raises(ValidationError, match="Describe the sound"):
        await service.generate_sounds(uuid4(), prompt="hi")


@pytest.mark.asyncio
async def test_sounds_shares_the_music_queue_cap(mute_blocklist) -> None:
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=False)
    service._active_generate_queue_count = AsyncMock(
        return_value=WEB_MUSIC_GENERATE_QUEUE_CAP_PAID
    )

    with pytest.raises(RateLimitedError, match=f"already have {WEB_MUSIC_GENERATE_QUEUE_CAP_PAID}"):
        await service.generate_sounds(uuid4(), prompt="a warm tape hiss")


@pytest.mark.asyncio
async def test_sounds_enqueues_with_kind_sounds(mute_blocklist) -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    task_id = uuid4()
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=False)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    service._reserve_daily_slot = AsyncMock(return_value=QUOTA)
    service._enqueue_web_generate = AsyncMock(return_value=task_id)
    service._link_generation_debit_reference = AsyncMock()
    service._resolve_workspace_id = AsyncMock(return_value=workspace_id)
    service._with_queue_fields = AsyncMock(return_value=QUOTA)
    service._open_charges = {}

    result = await service.generate_sounds(
        user_id,
        prompt="  a warm tape hiss with a soft tail  ",
        workspace_id=workspace_id,
    )

    assert result["task_id"] == str(task_id)
    assert result["status"] == "QUEUED"
    assert result["style"] == "a warm tape hiss with a soft tail"
    service._reserve_daily_slot.assert_awaited_once()
    call = service._enqueue_web_generate.await_args
    assert call.kwargs["kind"] == "sounds"
    assert call.kwargs["style"] == "a warm tape hiss with a soft tail"
    assert call.kwargs["instrumental"] is True
    assert call.kwargs["lyrics"] == ""


@pytest.mark.asyncio
async def test_fulfill_sounds_calls_the_sounds_endpoint() -> None:
    user_id = uuid4()
    task_id = uuid4()
    service = WebMusicService(MagicMock(), MagicMock())
    service._pool.fetchrow = AsyncMock(
        return_value={
            "id": task_id,
            "title": "Warm tape hiss",
            "lyrics": "",
            "style": "a warm tape hiss",
            "model": "V6_MINI",
            "instrumental": True,
            "external_task_id": None,
            "negative_tags": None,
            "vocal_gender": None,
            "style_weight": 0,
            "weirdness_constraint": 0,
            "audio_weight": 0,
            "reference_image_urls": [],
            "reference_video_urls": [],
            "persona_id": None,
            "kind": "sounds",
        }
    )
    service._pool.execute = AsyncMock()
    service._generation = MagicMock()
    service._generation.submit_suno_sounds = AsyncMock(return_value="job-1")
    service._generation.submit_suno_external_id = AsyncMock()
    service._link_generation_debit_reference = AsyncMock()
    service._open_charges = {}

    await service.fulfill_queued_generate(user_id, task_id, reservation_id="res-1")

    service._generation.submit_suno_sounds.assert_awaited_once_with(
        prompt="a warm tape hiss", model="V6_MINI"
    )
    service._generation.submit_suno_external_id.assert_not_awaited()
    update = service._pool.execute.await_args
    assert "external_task_id" in update.args[0]
