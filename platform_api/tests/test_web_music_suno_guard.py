"""Tests for web-music Suno title + blocklist pre-submit guards."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.suno_lyrics_sanitize import SunoRuntimeBlocklist
from platform_api.services.web_music_service import WebMusicService
from platform_api.services.web_music_suno_guard import (
    is_valid_web_music_title,
    prepare_web_music_title,
    raise_if_suno_blocklisted,
    sanitize_web_music_suno_fields,
)

_USER = UUID("11111111-1111-1111-1111-111111111111")
_RUNTIME = SunoRuntimeBlocklist(
    replacements={"lowlight": "afterglow"},
    block_terms=frozenset({"lowlight"}),
)


def test_prepare_title_strips_section_brackets() -> None:
    title = prepare_web_music_title(title="", lyrics="[Intro music]\nKhmer verse here")
    assert title == "Intro music"


def test_prepare_title_skips_generic_section_tag() -> None:
    title = prepare_web_music_title(title="", lyrics="[Verse 1]\nភ្លេងស្រណោះ")
    assert "ភ្លេង" in title
    assert "[" not in title


def test_khmer_title_is_valid() -> None:
    assert is_valid_web_music_title("ភ្លេងស្រណោះ")
    assert is_valid_web_music_title("Intro music")
    assert not is_valid_web_music_title("[Intro music]")
    assert not is_valid_web_music_title("")
    assert not is_valid_web_music_title("https://example.com")


def test_raise_if_blocklisted_rejects_lowlight() -> None:
    with pytest.raises(ValidationError, match="Suno-blocked") as exc:
        raise_if_suno_blocklisted(
            _RUNTIME,
            title="Night Song",
            lyrics="Pressure in the bleeding lowlight",
            style="Sad rock",
        )
    assert "lowlight" in str(exc.value.details["blocked_terms"]).lower()


def test_sanitize_strips_blocklist_wording() -> None:
    title, lyrics, style, tags = sanitize_web_music_suno_fields(
        _RUNTIME,
        title="lowlight nights",
        lyrics="the low-light room",
        style="pop",
        negative_tags="lowlight, metal",
    )
    assert "lowlight" not in title.lower()
    assert "low-light" not in lyrics.lower()
    assert "lowlight" not in tags.lower()


@pytest.mark.asyncio
async def test_generate_rejects_blocklist_before_charging() -> None:
    credit = AsyncMock()
    generation = AsyncMock()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    service = WebMusicService(pool, generation, credit_service=credit)
    blocklist = AsyncMock()
    blocklist.get_runtime_config = AsyncMock(return_value=_RUNTIME)
    with patch(
        "platform_api.dependencies.get_suno_blocklist_service",
        return_value=blocklist,
    ):
        with pytest.raises(ValidationError, match="Suno-blocked"):
            await service.generate(
                _USER,
                mode="advanced",
                lyrics="the lowlight fades away",
                style="pop",
                title="Night Song",
                instrumental=False,
                model="V5",
                prompt="",
            )
    credit.consume_credits.assert_not_called()
    generation.submit_suno.assert_not_called()


@pytest.mark.asyncio
async def test_generate_accepts_khmer_title_and_charges() -> None:
    credit = AsyncMock()
    generation = AsyncMock()
    generation.submit_suno = AsyncMock(
        return_value="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    service = WebMusicService(pool, generation, credit_service=credit)
    service._reserve_via_credits = AsyncMock(
        return_value={"limit": 50, "used": 10, "remaining": 4, "is_pro": False}
    )
    service._resolve_workspace_id = AsyncMock(return_value=_USER)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    blocklist = AsyncMock()
    blocklist.get_runtime_config = AsyncMock(
        return_value=SunoRuntimeBlocklist(block_terms=frozenset())
    )
    job_queue = AsyncMock()
    job_queue.enqueue = AsyncMock(return_value=None)
    with patch(
        "platform_api.dependencies.get_suno_blocklist_service",
        return_value=blocklist,
    ), patch(
        "platform_api.dependencies.get_job_queue_repo",
        return_value=job_queue,
    ):
        payload = await service.generate(
            _USER,
            mode="advanced",
            lyrics="ភ្លេងស្រណោះនៅយប់នេះ",
            style="Sad rock",
            title="ភ្លេងស្រណោះ",
            instrumental=False,
            model="V5_5",
            prompt="",
        )
    service._reserve_via_credits.assert_awaited()
    job_queue.enqueue.assert_awaited()
    assert payload["title"] == "ភ្លេងស្រណោះ"
    assert payload["status"] == "QUEUED"
