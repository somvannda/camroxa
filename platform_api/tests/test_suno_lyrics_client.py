"""Tests for Suno lyrics API client helpers."""

from __future__ import annotations

import pytest

from platform_api.clients.suno_client import (
    extract_suno_generate_task_id,
    extract_suno_lyrics_task_id,
    parse_suno_generate_poll,
    parse_suno_lyrics_poll,
)
from platform_api.exceptions import ExternalServiceError
from platform_api.services.generation_service import build_suno_lyrics_prompt


def test_extract_suno_lyrics_task_id_success() -> None:
    task_id = extract_suno_lyrics_task_id(
        {"code": 200, "msg": "success", "data": {"taskId": "abc123"}}
    )
    assert task_id == "abc123"


def test_extract_suno_generate_task_id_success() -> None:
    task_id = extract_suno_generate_task_id(
        {"code": 200, "msg": "success", "data": {"taskId": "gen-456"}}
    )
    assert task_id == "gen-456"


def test_extract_suno_generate_task_id_flat_legacy() -> None:
    task_id = extract_suno_generate_task_id({"taskId": "legacy-789"})
    assert task_id == "legacy-789"


def test_extract_suno_generate_task_id_api_error() -> None:
    with pytest.raises(ExternalServiceError, match="Insufficient Suno API credits"):
        extract_suno_generate_task_id({"code": 429, "msg": "Insufficient credits", "data": {}})


def test_extract_suno_generate_task_id_data_string() -> None:
    task_id = extract_suno_generate_task_id({"code": 200, "msg": "success", "data": "task-string"})
    assert task_id == "task-string"


def test_extract_suno_generate_task_id_surfaces_api_message() -> None:
    with pytest.raises(ExternalServiceError, match="style is required"):
        extract_suno_generate_task_id({"code": 200, "msg": "style is required", "data": {}})


def test_extract_suno_generate_task_id_nested_response() -> None:
    task_id = extract_suno_generate_task_id(
        {"code": 200, "msg": "success", "data": {"response": {"taskId": "nested-1"}}}
    )
    assert task_id == "nested-1"


def test_extract_suno_generate_task_id_missing_raises() -> None:
    with pytest.raises(ExternalServiceError, match="empty taskId"):
        extract_suno_generate_task_id({"code": 200, "msg": "", "data": {}})


def test_extract_suno_lyrics_task_id_missing_raises() -> None:
    with pytest.raises(ExternalServiceError, match="empty taskId"):
        extract_suno_lyrics_task_id({"code": 200, "msg": "success", "data": {}})


def test_parse_suno_lyrics_poll_pending() -> None:
    parsed = parse_suno_lyrics_poll(
        {"code": 200, "data": {"status": "PENDING", "response": {}}}
    )
    assert parsed.state == "pending"


def test_parse_suno_lyrics_poll_success() -> None:
    parsed = parse_suno_lyrics_poll(
        {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "data": [
                        {
                            "text": "[Verse]\nLine one\nLine two",
                            "title": "Night Drive",
                            "status": "complete",
                        }
                    ]
                },
            },
        }
    )
    assert parsed.state == "success"
    assert "Line one" in parsed.text
    assert parsed.title == "Night Drive"


def test_parse_suno_generate_poll_success() -> None:
    parsed = parse_suno_generate_poll(
        {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "data": [
                        {"audio_url": "https://cdn.example.com/ok.mp3"},
                        {"audioUrl": "https://cdn.example.com/alt.mp3"},
                    ]
                },
            },
        }
    )
    assert parsed.state == "success"
    assert parsed.audio_url_ok == "https://cdn.example.com/ok.mp3"
    assert parsed.audio_url_alt == "https://cdn.example.com/alt.mp3"


def test_parse_suno_generate_poll_pending() -> None:
    parsed = parse_suno_generate_poll({"code": 200, "data": {"status": "PENDING"}})
    assert parsed.state == "pending"


def test_build_suno_lyrics_prompt_respects_200_char_limit() -> None:
    prompt = build_suno_lyrics_prompt(
        mood="Bittersweet love song with intimate memories " * 5,
        title="Midnight Quiet",
        structure="Intro: slow build\nVerse: gritty\nChorus: hook\nDrop: energy",
        language="English",
        forced_opening="Rolling through the midnight rain",
        retry_hint="more distinct lines please",
    )
    assert len(prompt) <= 200
    assert "English" in prompt


def test_build_suno_lyrics_prompt_modes() -> None:
    from platform_api.services.generation_service import (
        STRUCTURE_MODE_AI_FREE,
        STRUCTURE_MODE_SUNO,
        STRUCTURE_MODE_TEMPLATE,
    )

    template = build_suno_lyrics_prompt(
        title="Neon Harbor",
        mood="late-night",
        structure="[Intro]\n[Verse]\n[Chorus]\n[Bridge]",
        language="en",
        structure_mode=STRUCTURE_MODE_TEMPLATE,
    )
    assert "Intro" in template
    assert "use your own section headers" not in template

    ai_free = build_suno_lyrics_prompt(
        title="Neon Harbor",
        mood="late-night",
        structure="[Intro]\n[Verse]\n[Chorus]\n[Bridge]",
        language="en",
        structure_mode=STRUCTURE_MODE_AI_FREE,
    )
    assert "prefer Intro-Verse-Chorus-Bridge" in ai_free

    suno = build_suno_lyrics_prompt(
        title="Neon Harbor",
        mood="late-night",
        structure="[Intro]\n[Verse]\n[Chorus]\n[Bridge]",
        language="en",
        structure_mode=STRUCTURE_MODE_SUNO,
    )
    assert "use your own section headers" in suno
    assert "prefer " not in suno
    assert "Intro, Verse" not in suno
