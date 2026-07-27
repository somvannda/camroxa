"""Tests for Suno MP3 download URL resolution."""

from __future__ import annotations

import pytest

from platform_api.clients.suno_client import (
    _extract_clip_audio_url,
    _extract_clip_download_url,
    parse_suno_generate_poll,
)
from platform_api.services.suno_audio_resolver import (
    callback_indicates_success,
    extract_callback_download_urls,
    extract_callback_task_id,
)


def test_extract_clip_download_url_prefers_source_audio_url() -> None:
    clip = {
        "stream_audio_url": "https://cdn.example.com/stream.m3u8",
        "audio_url": "https://cdn.example.com/audio.mp3",
        "source_audio_url": "https://cdn.example.com/source.mp3",
    }
    assert _extract_clip_download_url(clip) == "https://cdn.example.com/source.mp3"


def test_extract_clip_audio_url_falls_back_to_stream_when_no_download_url() -> None:
    clip = {"stream_audio_url": "https://cdn.example.com/stream.m3u8"}
    assert _extract_clip_audio_url(clip) == "https://cdn.example.com/stream.m3u8"


def test_normalize_http_download_url_rejects_none_literal() -> None:
    from platform_api.services.suno_audio_resolver import (
        build_download_url_candidates,
        normalize_http_download_url,
    )

    assert normalize_http_download_url("None") == ""
    assert normalize_http_download_url("null") == ""
    assert normalize_http_download_url("https://cdn.example.com/ok.mp3") == "https://cdn.example.com/ok.mp3"
    assert build_download_url_candidates("None", "https://cdn.example.com/ok.mp3") == [
        "https://cdn.example.com/ok.mp3"
    ]


def test_parse_suno_generate_poll_uses_download_urls() -> None:
    parsed = parse_suno_generate_poll(
        {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "data": [
                        {
                            "stream_audio_url": "https://cdn.example.com/stream-ok",
                            "source_audio_url": "https://cdn.example.com/ok.mp3",
                        },
                        {
                            "stream_audio_url": "https://cdn.example.com/stream-alt",
                            "source_audio_url": "https://cdn.example.com/alt.mp3",
                        },
                    ]
                },
            },
        }
    )
    assert parsed.state == "success"
    assert parsed.audio_url_ok == "https://cdn.example.com/ok.mp3"
    assert parsed.audio_url_alt == "https://cdn.example.com/alt.mp3"


def test_parse_suno_generate_poll_extracts_clip_metadata() -> None:
    parsed = parse_suno_generate_poll(
        {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "data": [
                        {
                            "id": "audio-ok-111",
                            "source_audio_url": "https://cdn.example.com/ok.mp3",
                            "image_url": "https://cdn.example.com/ok.jpg",
                            "duration": 142.5,
                            "tags": "edm, workout",
                        },
                        {
                            "id": "audio-alt-222",
                            "source_audio_url": "https://cdn.example.com/alt.mp3",
                            "image_url": "https://cdn.example.com/alt.jpg",
                            "duration": 138.0,
                            "tags": ["pop", "alt"],
                        },
                    ]
                },
            },
        }
    )
    assert parsed.state == "success"
    assert parsed.audio_url_ok == "https://cdn.example.com/ok.mp3"
    assert parsed.image_url_ok == "https://cdn.example.com/ok.jpg"
    assert parsed.audio_id_ok == "audio-ok-111"
    assert parsed.audio_id_alt == "audio-alt-222"
    assert parsed.duration_ok == 142.5
    assert parsed.tags_ok == "edm, workout"
    assert parsed.image_url_alt == "https://cdn.example.com/alt.jpg"
    assert parsed.duration_alt == 138.0
    assert "pop" in parsed.tags_alt


def test_extract_callback_download_urls_from_sunoapi_payload() -> None:
    parsed = extract_callback_download_urls(
        {
            "code": 200,
            "msg": "All generated successfully.",
            "data": {
                "callbackType": "complete",
                "task_id": "abc123",
                "data": [
                    {"id": "clip-ok", "source_audio_url": "https://cdn.example.com/ok.mp3"},
                    {"id": "clip-alt", "source_audio_url": "https://cdn.example.com/alt.mp3"},
                ],
            },
        }
    )
    assert parsed.audio_url_ok == "https://cdn.example.com/ok.mp3"
    assert parsed.audio_url_alt == "https://cdn.example.com/alt.mp3"
    assert parsed.audio_id_ok == "clip-ok"
    assert parsed.audio_id_alt == "clip-alt"


def test_callback_indicates_success_for_complete_callback_type() -> None:
    assert callback_indicates_success({"code": 200, "data": {"callbackType": "complete"}})


def test_extract_callback_task_id_from_nested_payload() -> None:
    assert extract_callback_task_id({"data": {"task_id": "task-42"}}) == "task-42"
