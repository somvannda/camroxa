"""G12/B-004: completed stem operations flatten to one typed stem list."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.web_music_service import WebMusicService


def _service() -> WebMusicService:
    return WebMusicService(AsyncMock(), AsyncMock(), redis=None)


def _operation(*, clips: list[dict], as_text: bool = False) -> dict:
    payload = {"clips": clips}
    return {
        "id": uuid4(),
        "task_id": uuid4(),
        "result_json": json.dumps(payload) if as_text else payload,
        "created_at": datetime(2026, 11, 10, 7, 0, tzinfo=UTC),
    }


def _clip(clip_id: str, title: str, group: str, url: str | None = "/audio.mp3") -> dict:
    return {
        "id": clip_id,
        "title": title,
        "audio_url": url,
        "image_url": "https://cdn.test/image.jpg",
        "duration": 163.8,
        "metadata": {"stem_type_group_name": group},
    }


@pytest.mark.asyncio
async def test_stems_flatten_clips_and_keep_one_row_each() -> None:
    service = _service()
    first = _operation(
        clips=[_clip("a", "(Vocals)", "Vocals"), _clip("b", "(Instrumental)", "Instrumental")]
    )
    second = _operation(clips=[_clip("a", "(Vocals again)", "Vocals"), _clip("c", "(Other)", "Other")])
    service._pool.fetch = AsyncMock(return_value=[first, second])

    result = await service.list_studio_stems(uuid4())

    assert [item["clip_id"] for item in result["items"]] == ["a", "b", "c"]
    vocals = result["items"][0]
    assert vocals["stem_type"] == "Vocals"
    assert vocals["audio_url"] == "/audio.mp3"
    assert vocals["duration_seconds"] == 163.8
    assert vocals["created_at"] == "2026-11-10T07:00:00+00:00"
    assert vocals["task_id"] == str(first["task_id"])


@pytest.mark.asyncio
async def test_stems_parse_text_results_and_drop_unplayable_clips() -> None:
    service = _service()
    row = _operation(
        clips=[_clip("a", "(Vocals)", "Vocals", url=None), _clip("b", "(Bass)", "Bass")],
        as_text=True,
    )
    service._pool.fetch = AsyncMock(return_value=[row])

    result = await service.list_studio_stems(uuid4())

    assert [item["clip_id"] for item in result["items"]] == ["b"]
