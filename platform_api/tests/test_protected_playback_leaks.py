"""Catalog and playlist JSON must never leak origin/storage audio URLs."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.streaming_catalog_service import StreamingCatalogService
from platform_api.services.web_music_service import WebMusicService


FORBIDDEN_SNIPPETS = (
    "cdn1.suno.ai",
    "backblazeb2.com",
    "storage_key",
    "suno_audio_id",
    "audio_url_ok",
)


def _assert_no_origin_leak(payload: object) -> None:
    text = str(payload)
    for snippet in FORBIDDEN_SNIPPETS:
        assert snippet not in text


@pytest.mark.asyncio
async def test_home_catalog_json_has_no_origin_urls() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    track_id = uuid4()
    service._repo.list_recent_published_tracks = AsyncMock(
        return_value=[
            {
                "id": track_id,
                "title": "Night Drive",
                "storage_key": "user/album/track-ok.mp3",
                "suno_audio_id": "abc-123",
                "package_status": "ready",
                "play_count": 1,
            }
        ]
    )
    service._repo.list_published_albums = AsyncMock(return_value=[])
    service._cover_url = AsyncMock(return_value=None)
    payload = await service.get_home()
    track = payload["recent_tracks"][0]
    _assert_no_origin_leak(track)
    assert track["package_status"] == "ready"
    assert "id" in track


@pytest.mark.asyncio
async def test_task_payload_play_urls_are_camxora_paths() -> None:
    service = WebMusicService(pool=AsyncMock(), generation_service=AsyncMock(), redis=None)
    task_id = uuid4()
    user_id = uuid4()
    row = {
        "id": task_id,
        "title": "Night Drive",
        "lyrics": "",
        "style": "edm",
        "model": "V5",
        "instrumental": False,
        "status": "SUCCESS",
        "error_message": None,
        "created_at": None,
        "negative_tags": None,
        "vocal_gender": None,
        "style_weight": None,
        "weirdness_constraint": None,
        "audio_weight": None,
        "image_url_ok": None,
        "image_url_alt": None,
        "duration_ok": 120,
        "duration_alt": 120,
        "package_status_ok": "ready",
        "package_status_alt": "none",
        "packaged_storage_key_ok": "web-music/x.cxa",
        "packaged_storage_key_alt": None,
        "b2_storage_key_ok": "web-music/x.mp3",
        "b2_storage_key_alt": None,
        "audio_url_ok": "https://cdn1.suno.ai/secret.mp3",
        "audio_url_alt": None,
    }
    payload = await service._task_payload(row, user_id)
    _assert_no_origin_leak(payload["clips"])
    assert payload["clips"][0]["audio_url"].startswith("/api/v3/web-music/generations/")
    assert "stream" in payload["clips"][0]["audio_url"]
    assert payload["clips"][0]["package_status"] == "ready"
