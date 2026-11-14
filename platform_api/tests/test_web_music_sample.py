"""Sample this song: resolve the source audio, store it, forward as audioUrls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
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
async def test_generate_stores_the_sample_audio_reference(mute_blocklist) -> None:
    user_id = uuid4()
    sample_id = uuid4()
    task_id = uuid4()
    workspace_id = uuid4()
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=False)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    service._pool.fetchrow = AsyncMock(
        return_value={
            "status": "success",
            "audio_url_ok": "https://cdn.example/ok.mp3",
            "audio_url_alt": "https://cdn.example/alt.mp3",
        }
    )
    service._reserve_daily_slot = AsyncMock(return_value=QUOTA)
    service._enqueue_web_generate = AsyncMock(return_value=task_id)
    service._link_generation_debit_reference = AsyncMock()
    service._resolve_workspace_id = AsyncMock(return_value=workspace_id)
    service._with_queue_fields = AsyncMock(return_value=QUOTA)
    service._open_charges = {}

    await service.generate(
        user_id,
        mode="advanced",
        lyrics="[Verse]\nNew words",
        style="synthwave",
        title="Sample Song",
        instrumental=False,
        model="V6_MINI",
        prompt="",
        sample_task_id=sample_id,
        sample_variant="alt",
    )

    call = service._enqueue_web_generate.await_args
    assert call.kwargs["reference_audio_urls"] == ["https://cdn.example/alt.mp3"]


@pytest.mark.asyncio
async def test_a_sample_that_is_not_ready_is_refused(mute_blocklist) -> None:
    service = WebMusicService(MagicMock(), MagicMock())
    service._pool.fetchrow = AsyncMock(
        return_value={"status": "pending", "audio_url_ok": None, "audio_url_alt": None}
    )
    with pytest.raises(ValidationError, match="not ready"):
        await service.generate(
            uuid4(),
            mode="advanced",
            lyrics="verse",
            style="pop",
            title="Sample Song",
            instrumental=False,
            model="V6_MINI",
            prompt="",
            sample_task_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_fulfill_forwards_the_sample_audio() -> None:
    user_id = uuid4()
    task_id = uuid4()
    service = WebMusicService(MagicMock(), MagicMock())
    service._pool.fetchrow = AsyncMock(
        return_value={
            "id": task_id,
            "title": "Sample Song",
            "lyrics": "verse",
            "style": "synthwave",
            "model": "V6_MINI",
            "instrumental": False,
            "external_task_id": None,
            "negative_tags": None,
            "vocal_gender": None,
            "style_weight": 0,
            "weirdness_constraint": 0,
            "audio_weight": 0,
            "reference_image_urls": [],
            "reference_video_urls": [],
            "reference_audio_urls": ["https://cdn.example/alt.mp3"],
            "persona_id": None,
            "kind": "music",
        }
    )
    service._pool.execute = AsyncMock()
    service._generation = MagicMock()
    service._generation.submit_suno_external_id = AsyncMock(return_value="job-1")
    service._link_generation_debit_reference = AsyncMock()
    service._open_charges = {}

    await service.fulfill_queued_generate(user_id, task_id, reservation_id="res-1")

    request = service._generation.submit_suno_external_id.await_args.args[0]
    assert request.audio_urls == ["https://cdn.example/alt.mp3"]
