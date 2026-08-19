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


def test_parse_suno_generate_poll_rewrites_suno_m4a_to_mp3() -> None:
    clip_id = "441cb4bf-f013-4c88-8ea1-9d17499b1762"
    parsed = parse_suno_generate_poll(
        {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "data": [
                        {
                            "id": clip_id,
                            "source_audio_url": f"https://cdn1.suno.ai/{clip_id}.m4a",
                        }
                    ]
                },
            },
        }
    )
    assert parsed.state == "success"
    assert parsed.audio_url_ok == f"https://cdn1.suno.ai/{clip_id}.mp3"
    assert parsed.audio_id_ok == clip_id


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
                    {"id": "clip-ok", "source_audio_url": "https://cdn.example.com/ok.mp3", "duration": 199.0},
                    {"id": "clip-alt", "source_audio_url": "https://cdn.example.com/alt.mp3", "duration": 201.0},
                ],
            },
        }
    )
    assert parsed.audio_url_ok == "https://cdn.example.com/ok.mp3"
    assert parsed.audio_url_alt == "https://cdn.example.com/alt.mp3"
    assert parsed.audio_id_ok == "clip-ok"
    assert parsed.audio_id_alt == "clip-alt"
    assert parsed.duration_ok == 199.0
    assert parsed.duration_alt == 201.0


def test_extract_callback_synthesizes_cdn_url_when_clip_has_id_only() -> None:
    parsed = extract_callback_download_urls(
        {
            "code": 200,
            "data": {
                "callbackType": "complete",
                "data": [
                    {"id": "clip-ok", "source_audio_url": "https://cdn.example.com/ok.mp3"},
                    {"id": "25d27d13-10a9-4b73-9e2e-b344da4cf0c8"},
                ],
            },
        }
    )
    assert parsed.audio_url_ok == "https://cdn.example.com/ok.mp3"
    assert parsed.audio_id_alt == "25d27d13-10a9-4b73-9e2e-b344da4cf0c8"
    assert (
        parsed.audio_url_alt
        == "https://cdn1.suno.ai/25d27d13-10a9-4b73-9e2e-b344da4cf0c8.mp3"
    )


def test_cdn_url_for_suno_audio_id() -> None:
    from platform_api.clients.suno_client import cdn_url_for_suno_audio_id, coerce_suno_download_url

    assert cdn_url_for_suno_audio_id("abc-123") == "https://cdn1.suno.ai/abc-123.mp3"
    assert coerce_suno_download_url(url="", audio_id="abc-123") == "https://cdn1.suno.ai/abc-123.mp3"
    assert coerce_suno_download_url(url="https://cdn.example.com/x.mp3", audio_id="abc") == (
        "https://cdn.example.com/x.mp3"
    )


def test_coerce_suno_download_url_rewrites_cdn_m4a_to_mp3() -> None:
    from platform_api.clients.suno_client import coerce_suno_download_url, prefer_suno_mpeg_cdn_url

    m4a = "https://cdn1.suno.ai/441cb4bf-f013-4c88-8ea1-9d17499b1762.m4a"
    mp3 = "https://cdn1.suno.ai/441cb4bf-f013-4c88-8ea1-9d17499b1762.mp3"
    assert prefer_suno_mpeg_cdn_url(m4a) == mp3
    assert coerce_suno_download_url(url=m4a) == mp3
    assert coerce_suno_download_url(url=mp3) == mp3
    assert coerce_suno_download_url(url="https://cdn.example.com/clip.m4a") == (
        "https://cdn.example.com/clip.m4a"
    )


def test_extract_clip_download_url_rewrites_suno_m4a() -> None:
    clip = {
        "id": "441cb4bf-f013-4c88-8ea1-9d17499b1762",
        "source_audio_url": "https://cdn1.suno.ai/441cb4bf-f013-4c88-8ea1-9d17499b1762.m4a",
        "audio_url": "https://cdn1.suno.ai/441cb4bf-f013-4c88-8ea1-9d17499b1762.mp3",
    }
    assert (
        _extract_clip_download_url(clip)
        == "https://cdn1.suno.ai/441cb4bf-f013-4c88-8ea1-9d17499b1762.mp3"
    )


def test_payload_is_mpeg_audio_rejects_iso_bmff() -> None:
    from platform_api.clients.suno_client import payload_is_mpeg_audio

    assert payload_is_mpeg_audio(b"ID3" + b"\x00" * 300) is True
    assert payload_is_mpeg_audio(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 300) is False
    assert payload_is_mpeg_audio(b"ID3") is False


def test_is_disallowed_suno_audio_url_rejects_m4a_and_hls() -> None:
    from platform_api.services.suno_audio_resolver import (
        build_download_url_candidates,
        is_disallowed_suno_audio_url,
        validate_mp3_bytes,
    )

    assert is_disallowed_suno_audio_url("https://cdn.example.com/track.m4a") is True
    assert is_disallowed_suno_audio_url("https://cdn.example.com/stream.m3u8") is True
    assert is_disallowed_suno_audio_url("https://cdn1.suno.ai/abc.mp3") is False
    assert build_download_url_candidates(
        "https://cdn.example.com/track.m4a",
        "https://cdn.example.com/ok.mp3",
    ) == ["https://cdn.example.com/ok.mp3"]
    assert validate_mp3_bytes(b"ID3" + b"x" * 100) is True
    assert validate_mp3_bytes(b"\xff\xfb" + b"x" * 100) is True
    assert validate_mp3_bytes(b"\x00\x00\x00\x18ftypmp42") is False


def test_payload_is_wav_audio() -> None:
    from platform_api.services.suno_audio_resolver import payload_is_wav_audio, validate_wav_bytes

    wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"fmt "
    assert payload_is_wav_audio(wav)
    assert validate_wav_bytes(wav)
    assert payload_is_wav_audio(b"ID3" + b"x" * 20) is False


def test_parse_suno_wav_poll_keeps_pending_on_non_200() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, error = parse_suno_wav_poll({"code": 404, "msg": "not found"})
    assert status == "pending"
    assert url is None
    assert error is None


def test_parse_suno_wav_poll_success_url() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, error = parse_suno_wav_poll(
        {
            "code": 200,
            "data": {"status": "SUCCESS", "audioWavUrl": "https://cdn.example.com/clip.wav"},
        }
    )
    assert status == "success"
    assert url == "https://cdn.example.com/clip.wav"
    assert error is None


def test_extract_suno_wav_task_id_accepts_string_code() -> None:
    from platform_api.clients.suno_client import extract_suno_wav_task_id

    task_id = extract_suno_wav_task_id({"code": "200", "data": {"taskId": "wav-1"}})
    assert task_id == "wav-1"


@pytest.mark.asyncio
async def test_download_suno_wav_bytes_accepts_mislabelled_mp4_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.services import suno_audio_resolver as resolver

    wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"fmt " + b"\x00" * 16

    class FakeResponse:
        headers = {"content-type": "audio/mp4"}

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self, chunk_size: int = 65536):
            yield wav

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        def stream(self, method: str, url: str):
            del method, url
            return FakeResponse()

    monkeypatch.setattr(resolver.httpx, "AsyncClient", FakeClient)
    data = await resolver.download_suno_wav_bytes("https://cdn.example.com/clip.wav")
    assert data[:4] == b"RIFF"


@pytest.mark.asyncio
async def test_origin_audio_range_is_playable_accepts_partial_content(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.services import suno_audio_resolver as resolver

    class FakeResponse:
        status_code = 206
        content = b"ID3" + b"\x00" * 80

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def get(self, url: str, headers: dict[str, str] | None = None):
            del url, headers
            return FakeResponse()

    monkeypatch.setattr(resolver.httpx, "AsyncClient", FakeClient)
    assert await resolver.origin_audio_range_is_playable("https://cdn1.suno.ai/clip.mp3") is True


@pytest.mark.asyncio
async def test_origin_audio_range_is_playable_rejects_cdn_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.services import suno_audio_resolver as resolver

    class FakeResponse:
        status_code = 403
        content = b"Forbidden"

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def get(self, url: str, headers: dict[str, str] | None = None):
            del url, headers
            return FakeResponse()

    monkeypatch.setattr(resolver.httpx, "AsyncClient", FakeClient)
    assert await resolver.origin_audio_range_is_playable("https://cdn1.suno.ai/clip.mp3") is False


def test_callback_indicates_success_for_complete_callback_type() -> None:
    assert callback_indicates_success({"code": 200, "data": {"callbackType": "complete"}})


def test_extract_callback_task_id_from_nested_payload() -> None:
    assert extract_callback_task_id({"data": {"task_id": "task-42"}}) == "task-42"
