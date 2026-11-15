"""Simple mode sends one description; Suno writes the title and the lyrics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.clients.suno_client import parse_suno_generate_poll
from platform_api.services.web_music_service import (
    WebMusicService,
    build_web_simple_description,
)


class TestDescriptionBuilder:
    def test_keeps_the_angle_and_drops_nothing_suno_needs(self) -> None:
        text = build_web_simple_description(
            {
                "prompt": "eurodance, hands up, 142 BPM, four-on-the-floor kick",
                "theme": "a rooftop sunrise after the party",
                "structure": "Chorus, Verse, Chorus",
                "title": "",
            }
        )
        assert "eurodance, hands up" in text
        assert "rooftop sunrise" in text
        assert "Chorus, Verse, Chorus" in text
        assert len(text) <= 2000

    def test_survives_an_empty_brief(self) -> None:
        assert build_web_simple_description({}) == "An original song"

    def test_quotes_a_listener_title(self) -> None:
        text = build_web_simple_description({"prompt": "lofi", "title": "Night Bus"})
        assert 'Title it "Night Bus"' in text


def _description_poll() -> dict:
    return {
        "code": 200,
        "data": {
            "status": "SUCCESS",
            "response": {
                "data": [
                    {
                        "id": "clip-1",
                        "audio_url": "https://cdn.example/a.mp3",
                        "metadata": {
                            "title": "The Long Way Home",
                            "prompt": "[Verse]\ncity lights",
                        },
                    },
                    {
                        "id": "clip-2",
                        "audio_url": "https://cdn.example/b.mp3",
                        "metadata": {
                            "title": "The Long Way Home",
                            "prompt": "[Verse]\ncity lights",
                        },
                    },
                ]
            },
        },
    }


def test_poll_carries_suno_title_and_lyrics() -> None:
    parsed = parse_suno_generate_poll(_description_poll())

    assert parsed.state == "success"
    assert parsed.title_ok == "The Long Way Home"
    assert parsed.title_alt == "The Long Way Home"
    assert "city lights" in parsed.lyrics


@pytest.mark.asyncio
async def test_completed_description_song_stores_title_and_lyrics() -> None:
    task_id = uuid4()
    service = WebMusicService(AsyncMock(), MagicMock())
    service._pool.execute = AsyncMock()
    service._upload_service = MagicMock()
    service._upload_service.schedule_web_music_b2_backfill = MagicMock()
    service._poll_pending_coalesced = AsyncMock(
        return_value=parse_suno_generate_poll(_description_poll())
    )

    await service._refresh_pending_from_suno(
        {"id": task_id, "status": "pending", "external_task_id": "ext-1"}
    )

    updates = [
        call.args
        for call in service._pool.execute.await_args_list
        if "title_ok = COALESCE" in str(call.args[0])
    ]
    assert updates, "the polled title/lyrics were never persisted"
    args = updates[0]
    assert args[11] == "The Long Way Home"  # title_ok
    assert "city lights" in args[13]  # lyrics


@pytest.mark.asyncio
async def test_queue_submits_a_description_not_lyrics() -> None:
    """The worker must hand Suno the description and let it write the lyrics."""
    user_id = uuid4()
    task_id = uuid4()
    generation = MagicMock()
    generation.submit_suno_external_id = AsyncMock(return_value="ext-1")
    service = WebMusicService(AsyncMock(), generation)
    service._pool.fetchrow = AsyncMock(
        return_value={
            "id": task_id,
            "title": "Untitled",
            "lyrics": "",
            "style": "Eurodance",
            "model": "V6",
            "instrumental": False,
            "external_task_id": None,
            "negative_tags": None,
            "vocal_gender": None,
            "style_weight": None,
            "weirdness_constraint": None,
            "audio_weight": None,
            "reference_image_urls": "[]",
            "reference_video_urls": "[]",
            "persona_id": None,
            "kind": "music",
            "status": "pending",
            "lyrics_brief": {
                "prompt": "eurodance, hands up",
                "theme": "a late train home",
                "structure": "",
                "title": "",
            },
        }
    )
    service._pool.execute = AsyncMock()

    await service.fulfill_queued_generate(user_id, task_id, reservation_id="res-1")

    request = generation.submit_suno_external_id.await_args.args[0]
    assert "eurodance, hands up" in request.description
    assert "late train home" in request.description
