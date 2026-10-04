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


def test_extract_clip_download_url_prefers_callback_audio_url() -> None:
    clip = {
        "stream_audio_url": "https://cdn.example.com/stream.m3u8",
        "audio_url": "https://tempfile.aiquickdraw.com/audio.mp3",
        "source_audio_url": "https://cdn1.suno.ai/clip-id.mp3",
    }
    assert _extract_clip_download_url(clip) == "https://tempfile.aiquickdraw.com/audio.mp3"


def test_extract_clip_download_url_prefers_camelcase_audio_url() -> None:
    clip = {
        "audioUrl": "https://tempfile.aiquickdraw.com/ok.mp3",
        "sourceAudioUrl": "https://cdn1.suno.ai/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.mp3",
    }
    assert _extract_clip_download_url(clip) == "https://tempfile.aiquickdraw.com/ok.mp3"


def test_extract_callback_download_urls_prefers_camelcase_audio_url() -> None:
    clip_id = "952982b2-f134-4ac6-a3d2-aa1404df1ee9"
    parsed = extract_callback_download_urls(
        {
            "code": 200,
            "msg": "All generated successfully.",
            "data": {
                "callbackType": "complete",
                "task_id": "task-1",
                "data": [
                    {
                        "id": clip_id,
                        "audioUrl": f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3",
                        "sourceAudioUrl": f"https://cdn1.suno.ai/{clip_id}.mp3",
                        "streamAudioUrl": "https://musicfile.removeai.ai/stream-ok",
                    },
                    {
                        "id": "clip-alt",
                        "audioUrl": "https://tempfile.aiquickdraw.com/r/clip-alt.mp3",
                        "sourceAudioUrl": "https://cdn1.suno.ai/clip-alt.mp3",
                    },
                ],
            },
        }
    )
    assert parsed.audio_url_ok == f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3"
    assert parsed.audio_url_alt == "https://tempfile.aiquickdraw.com/r/clip-alt.mp3"
    assert parsed.audio_id_ok == clip_id


def test_parse_suno_generate_poll_prefers_callback_audio_url() -> None:
    clip_id = "952982b2-f134-4ac6-a3d2-aa1404df1ee9"
    parsed = parse_suno_generate_poll(
        {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "data": [
                        {
                            "id": clip_id,
                            "audioUrl": f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3",
                            "sourceAudioUrl": f"https://cdn1.suno.ai/{clip_id}.mp3",
                        }
                    ]
                },
            },
        }
    )
    assert parsed.state == "success"
    assert parsed.audio_url_ok == f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3"


def test_extract_clip_download_url_falls_back_to_source_audio_url() -> None:
    clip = {
        "stream_audio_url": "https://cdn.example.com/stream.m3u8",
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
    assert parsed.audio_url_ok == f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3"
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
        == "https://tempfile.aiquickdraw.com/r/25d27d13-10a9-4b73-9e2e-b344da4cf0c8.mp3"
    )


def test_cdn_url_for_suno_audio_id() -> None:
    from platform_api.clients.suno_client import cdn_url_for_suno_audio_id, coerce_suno_download_url

    assert cdn_url_for_suno_audio_id("abc-123") == "https://tempfile.aiquickdraw.com/r/abc-123.mp3"
    assert coerce_suno_download_url(url="", audio_id="abc-123") == (
        "https://tempfile.aiquickdraw.com/r/abc-123.mp3"
    )
    assert coerce_suno_download_url(url="https://cdn.example.com/x.mp3", audio_id="abc") == (
        "https://cdn.example.com/x.mp3"
    )


def test_coerce_suno_download_url_rewrites_cdn_m4a_to_mp3() -> None:
    from platform_api.clients.suno_client import coerce_suno_download_url, prefer_suno_mpeg_cdn_url

    clip_id = "441cb4bf-f013-4c88-8ea1-9d17499b1762"
    m4a = f"https://cdn1.suno.ai/{clip_id}.m4a"
    mp3 = f"https://cdn1.suno.ai/{clip_id}.mp3"
    tempfile = f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3"
    assert prefer_suno_mpeg_cdn_url(m4a) == tempfile
    assert coerce_suno_download_url(url=m4a) == tempfile
    assert coerce_suno_download_url(url=mp3) == tempfile
    signed = f"https://cdn1.suno.ai/{clip_id}.mp3?Key-Pair-Id=K&Signature=s&Policy=p"
    assert coerce_suno_download_url(url=signed) == signed
    assert coerce_suno_download_url(url="https://cdn.example.com/clip.m4a") == (
        "https://cdn.example.com/clip.m4a"
    )


def test_extract_clip_download_url_rewrites_suno_m4a() -> None:
    clip_id = "441cb4bf-f013-4c88-8ea1-9d17499b1762"
    clip = {
        "id": clip_id,
        "source_audio_url": f"https://cdn1.suno.ai/{clip_id}.m4a",
        "audio_url": f"https://cdn1.suno.ai/{clip_id}.mp3",
    }
    assert _extract_clip_download_url(clip) == f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3"


def test_extract_clip_download_url_rejects_musicfile_and_stores_tempfile() -> None:
    clip_id = "952982b2-f134-4ac6-a3d2-aa1404df1ee9"
    clip = {
        "id": clip_id,
        # musicfile.removeai.ai is the cover host (0-byte/JPEG), not the MP3.
        "audioUrl": "https://musicfile.removeai.ai/Y2Y0YWU2MmI",
        "audio_url": f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3",
    }
    assert _extract_clip_download_url(clip) == f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3"


def test_extract_clip_download_url_musicfile_only_synthesizes_tempfile() -> None:
    clip_id = "952982b2-f134-4ac6-a3d2-aa1404df1ee9"
    clip = {
        "id": clip_id,
        "audioUrl": "https://musicfile.removeai.ai/Y2Y0YWU2MmI",
        "sourceAudioUrl": "https://cdn1.suno.ai/unsigned.mp3",
    }
    assert _extract_clip_download_url(clip) == f"https://tempfile.aiquickdraw.com/r/{clip_id}.mp3"


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
    assert is_disallowed_suno_audio_url("https://musicfile.removeai.ai/Y2Y0YWU2MmI.mp3") is True
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


def test_parse_suno_wav_poll_reads_musicapi_envelope_string() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, error = parse_suno_wav_poll(
        {
            "code": 200,
            "msg": "success",
            "data": {
                "status": "SUCCESS",
                "response": {"taskId": "w1", "sunoData": ["https://b2.example.com/wav/clip.wav"]},
            },
        }
    )
    assert status == "success"
    assert url == "https://b2.example.com/wav/clip.wav"
    assert error is None


def test_parse_suno_wav_poll_reads_musicapi_download_url_object() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, _error = parse_suno_wav_poll(
        {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "sunoData": [
                        {
                            "clip_id": "c1",
                            "format": "wav",
                            "download_url": "https://b2.example.com/c1.wav",
                        }
                    ]
                },
            },
        }
    )
    assert status == "success"
    assert url == "https://b2.example.com/c1.wav"


def test_parse_suno_wav_poll_musicapi_pending_has_no_url() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, _error = parse_suno_wav_poll({"code": 200, "data": {"status": "PENDING"}})
    assert status == "pending"
    assert url is None


def test_recovery_tracks_flattens_both_provider_shapes() -> None:
    from platform_api.services.suno_audio_resolver import _recovery_tracks

    assert _recovery_tracks(
        {"status": "SUCCESS", "response": {"sunoData": [{"id": "c1", "audio_url": "u1"}]}}
    ) == [{"id": "c1", "audio_url": "u1"}]
    assert _recovery_tracks([{"id": "c2"}]) == [{"id": "c2"}]
    assert _recovery_tracks({"response": {"data": [{"id": "c3"}]}}) == [{"id": "c3"}]
    assert _recovery_tracks({"nothing": True}) == []


@pytest.mark.asyncio
async def test_submit_task_instrumental_gets_placeholder_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from platform_api.clients.suno_client import SunoClient

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"code": 200, "data": {"taskId": "t1"}}

    class FakeClient:
        async def post(self, path: str, json: dict[str, object] | None = None) -> FakeResponse:
            captured["path"] = path
            captured["json"] = json
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    settings = SimpleNamespace(
        suno_api_base_url="https://musicapi.camxora.com",
        suno_callback_base_url="",
        suno_timeout_seconds=30,
    )
    client = SunoClient(settings)
    monkeypatch.setattr(client, "_build_client", lambda api_key: FakeClient())

    await client.submit_task(
        model="V6", title="T", lyrics="", style="lofi", instrumental=True, api_key="k"
    )
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["prompt"] == "[Instrumental]"
    assert payload["lyrics"] == ""

    await client.submit_task(
        model="V6", title="T", lyrics="la la", style="pop", instrumental=False, api_key="k"
    )
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["prompt"] == "la la"


@pytest.mark.asyncio
async def test_poll_suno_generate_tries_next_key_on_owner_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.clients.suno_client import SunoClient
    from platform_api.exceptions import ExternalServiceError
    from platform_api.services import suno_audio_resolver as resolver

    async def fake_keys(_pool: object) -> list[str]:
        return ["owner", "other"]

    calls: list[str] = []

    async def fake_check_status(self: SunoClient, task_id: str, *, api_key: str | None = None):
        del self, task_id
        calls.append(str(api_key))
        if api_key == "owner":
            raise ExternalServiceError(
                "Suno API error 403", is_retryable=False, details={"status_code": 403}
            )
        return {
            "code": 200,
            "data": {
                "status": "SUCCESS",
                "response": {
                    "sunoData": [{"id": "c1", "audio_url": "https://b2.example.com/c1.mp3"}]
                },
            },
        }

    monkeypatch.setattr(resolver, "active_suno_key_values", fake_keys)
    monkeypatch.setattr(SunoClient, "check_status", fake_check_status)

    parsed = await resolver.poll_suno_generate_with_pool(object(), "task-1")
    assert parsed.state == "success"
    assert parsed.audio_url_ok == "https://b2.example.com/c1.mp3"
    assert calls == ["owner", "other"]


@pytest.mark.asyncio
async def test_call_with_owning_suno_key_skips_non_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.exceptions import ExternalServiceError
    from platform_api.services import suno_audio_resolver as resolver

    async def fake_keys(_pool: object) -> list[str]:
        return ["a", "b", "c"]

    monkeypatch.setattr(resolver, "active_suno_key_values", fake_keys)
    seen: list[str] = []

    async def fn(key: str) -> str:
        seen.append(key)
        if key in {"a", "b"}:
            raise ExternalServiceError(
                "Suno API error 403", is_retryable=False, details={"status_code": 403}
            )
        return f"ok-{key}"

    result, used = await resolver.call_with_owning_suno_key(object(), fn)
    assert result == "ok-c"
    assert used == "c"
    assert seen == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_call_with_owning_suno_key_reraises_real_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.exceptions import ExternalServiceError
    from platform_api.services import suno_audio_resolver as resolver

    async def fake_keys(_pool: object) -> list[str]:
        return ["a"]

    monkeypatch.setattr(resolver, "active_suno_key_values", fake_keys)

    async def fn(key: str) -> str:
        raise ExternalServiceError(
            "Suno API error 500", is_retryable=True, details={"status_code": 500}
        )

    with pytest.raises(ExternalServiceError):
        await resolver.call_with_owning_suno_key(object(), fn)


def test_parse_suno_wav_poll_successflag_success() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, _error = parse_suno_wav_poll(
        {
            "code": 200,
            "data": {
                "successFlag": "SUCCESS",
                "response": {"audioWavUrl": "https://b2.example.com/c1.wav"},
            },
        }
    )
    assert status == "success"
    assert url == "https://b2.example.com/c1.wav"


def test_parse_suno_wav_poll_successflag_failed() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, error = parse_suno_wav_poll(
        {
            "code": 200,
            "data": {
                "successFlag": "GENERATE_WAV_FAILED",
                "response": {"audioWavUrl": None},
                "errorMessage": "conversion failed",
            },
        }
    )
    assert status == "failed"
    assert url is None
    assert error


def test_parse_suno_wav_poll_successflag_pending() -> None:
    from platform_api.clients.suno_client import parse_suno_wav_poll

    status, url, _error = parse_suno_wav_poll(
        {"code": 200, "data": {"successFlag": "PENDING", "response": {"audioWavUrl": None}}}
    )
    assert status == "pending"
    assert url is None


@pytest.mark.asyncio
async def test_recover_suno_task_download_urls_reads_data_task_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """musicapi's recovery create returns data.task_id (snake) then a track list."""
    from platform_api.services import suno_audio_resolver as resolver

    async def fake_keys(_pool: object) -> list[str]:
        return ["k1"]

    monkeypatch.setattr(resolver, "active_suno_key_values", fake_keys)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", no_sleep)

    state = {"polls": 0}

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def post(self, url: str, headers: object = None, json: object = None) -> FakeResponse:
            return FakeResponse({"code": 200, "msg": "success", "data": {"task_id": "rt1"}})

        async def get(self, url: str, headers: object = None, params: object = None) -> FakeResponse:
            state["polls"] += 1
            if state["polls"] == 1:
                return FakeResponse({"code": 201, "task_id": "rt1", "msg": "success", "data": None})
            return FakeResponse(
                {
                    "code": 200,
                    "task_id": "rt1",
                    "msg": "success",
                    "data": [
                        {"id": "c1", "audio_url": "https://b2.example.com/c1.wav", "status": "success"},
                        {"id": None, "audio_url": "", "status": "failed"},
                    ],
                }
            )

    monkeypatch.setattr(resolver.httpx, "AsyncClient", FakeAsyncClient)

    mapping = await resolver.recover_suno_task_download_urls(object(), "task-1")
    assert mapping == {"c1": "https://b2.example.com/c1.wav"}
    assert state["polls"] == 2
