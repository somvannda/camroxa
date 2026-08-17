"""Tests for web music style prompt builder."""

from __future__ import annotations

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.web_music_service import build_web_music_style_user_prompt


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
