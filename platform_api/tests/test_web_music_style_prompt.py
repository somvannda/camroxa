"""Tests for web music style prompt builder."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from platform_api.exceptions import ExternalServiceError, ValidationError
from platform_api.routers.web_music import WebMusicStyleRequest
from platform_api.services.web_music_service import (
    build_web_music_style_user_prompt,
    reraise_text_assist_failure,
)


def test_build_style_prompt_prioritizes_styles_field() -> None:
    text = build_web_music_style_user_prompt(
        style="pop, guitar",
        lyrics="[Verse]\nHello world",
        title="Summer Night",
    )
    assert "User's current Styles field" in text
    assert "pop, guitar" in text
    assert "Summer Night" in text
    assert "Hello world" in text
    assert "do not quote lyrics" in text.lower()


def test_build_style_prompt_accepts_legacy_prompt_only() -> None:
    text = build_web_music_style_user_prompt(prompt="lo-fi chill")
    assert "lo-fi chill" in text


def test_build_style_prompt_requires_some_input() -> None:
    with pytest.raises(ValidationError):
        build_web_music_style_user_prompt()


def test_style_request_accepts_full_lyrics_field() -> None:
    body = WebMusicStyleRequest(style="pop", lyrics="x" * 5000)
    assert len(body.lyrics) == 5000


def test_style_request_rejects_lyrics_over_limit() -> None:
    with pytest.raises(PydanticValidationError):
        WebMusicStyleRequest(lyrics="x" * 5001)


def test_reraise_text_assist_failure_maps_provider_errors() -> None:
    with pytest.raises(ExternalServiceError, match="temporarily unavailable") as exc_info:
        reraise_text_assist_failure(ExternalServiceError("DeepSeek timeout", is_retryable=True))
    assert exc_info.value.status_code == 502


def test_reraise_text_assist_failure_preserves_validation() -> None:
    with pytest.raises(ValidationError, match="Add style tags"):
        reraise_text_assist_failure(
            ValidationError("Add style tags or a song description before generating styles.")
        )
