"""Add-to-playlist must accept packaged clips (origin URLs are cleared)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.models.products import SUNO_TASK_SOURCE_WEB_MUSIC
from platform_api.services.web_music_service import WebMusicService


@pytest.mark.asyncio
async def test_add_playlist_item_accepts_packaged_clip_without_origin_url() -> None:
    user_id = uuid4()
    playlist_id = uuid4()
    task_id = uuid4()
    item_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": task_id,
                "title": "Neon After Midnight",
                "style": "edm",
                "status": "SUCCESS",
                "audio_url_ok": None,
                "audio_url_alt": None,
                "image_url_ok": None,
                "image_url_alt": None,
                "b2_storage_key_ok": "web-music/x.mp3",
                "b2_storage_key_alt": None,
                "package_status_ok": "ready",
                "package_status_alt": "ready",
                "packaged_storage_key_ok": "web-music/x.cxa",
                "packaged_storage_key_alt": "web-music/x-alt.cxa",
            },
            {
                "id": item_id,
                "suno_task_id": task_id,
                "variant": "ok",
                "position": 1,
                "added_at": datetime(2026, 8, 21, tzinfo=timezone.utc),
            },
        ]
    )
    pool.fetchval = AsyncMock(return_value=1)
    pool.execute = AsyncMock(return_value="UPDATE 1")
    service = WebMusicService(pool=pool, generation_service=AsyncMock(), redis=None)
    service.get_playlist = AsyncMock(return_value={"id": str(playlist_id), "name": "EDM"})
    service._mint_owner_play_url = AsyncMock(return_value="/api/v1/web-music/play/token")

    item = await service.add_playlist_item(user_id, playlist_id, task_id=task_id, variant="ok")

    assert item["task_id"] == str(task_id)
    assert item["ready"] is True
    assert item["package_status"] == "ready"
    assert item["audio_url"].startswith("/api/v1/web-music/play/")
    suno_query = pool.fetchrow.await_args_list[0]
    assert SUNO_TASK_SOURCE_WEB_MUSIC in suno_query.args


@pytest.mark.asyncio
async def test_add_playlist_item_still_rejects_unready_clip() -> None:
    user_id = uuid4()
    playlist_id = uuid4()
    task_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": task_id,
            "title": "WIP",
            "style": "pop",
            "status": "SUCCESS",
            "audio_url_ok": None,
            "audio_url_alt": None,
            "image_url_ok": None,
            "image_url_alt": None,
            "b2_storage_key_ok": None,
            "b2_storage_key_alt": None,
            "package_status_ok": "none",
            "package_status_alt": "none",
            "packaged_storage_key_ok": None,
            "packaged_storage_key_alt": None,
        }
    )
    service = WebMusicService(pool=pool, generation_service=AsyncMock(), redis=None)
    service.get_playlist = AsyncMock(return_value={"id": str(playlist_id), "name": "Rap"})

    with pytest.raises(ValidationError, match="not ready"):
        await service.add_playlist_item(user_id, playlist_id, task_id=task_id, variant="ok")
