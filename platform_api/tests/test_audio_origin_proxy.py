from __future__ import annotations

import httpx
import pytest

from platform_api.exceptions import NotFoundError
from platform_api.services.audio_origin_proxy import (
    is_camxora_audio_proxy_url,
    is_initial_play_range,
    proxy_origin_audio,
)


def test_is_initial_play_range() -> None:
    assert is_initial_play_range(None) is True
    assert is_initial_play_range("bytes=0-") is True
    assert is_initial_play_range("bytes=0-1023") is True
    assert is_initial_play_range("bytes=1024-2047") is False


def test_is_camxora_audio_proxy_url() -> None:
    assert is_camxora_audio_proxy_url("/api/v1/web-music/play/abc_DEF-123") is True
    assert is_camxora_audio_proxy_url(
        "/api/v1/web-music/generations/441cb4bf-f013-4c88-8ea1-9d17499b1762/stream/ok"
    )
    assert is_camxora_audio_proxy_url(
        "/api/v1/web-music/generations/441cb4bf-f013-4c88-8ea1-9d17499b1762/stream/alt"
    )
    assert (
        is_camxora_audio_proxy_url(
            "https://music.sandbox.camxora.com/api/v1/public/streaming/tracks/"
            "441cb4bf-f013-4c88-8ea1-9d17499b1762/stream"
        )
        is True
    )
    assert is_camxora_audio_proxy_url("https://cdn1.suno.ai/abc-123.mp3") is False
    assert is_camxora_audio_proxy_url("https://s3.us-west-004.backblazeb2.com/secret.mp3") is False
    assert is_camxora_audio_proxy_url("/api/v1/web-music/generations/x/download") is False
    assert is_camxora_audio_proxy_url("/static/track.mp3") is False


@pytest.mark.asyncio
async def test_proxy_origin_audio_forwards_range_and_hides_location(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeStream:
        status_code = 206
        headers = httpx.Headers(
            {
                "content-type": "audio/mpeg",
                "content-range": "bytes 0-10/100",
                "accept-ranges": "bytes",
                "location": "https://cdn1.suno.ai/secret.mp3",
                "set-cookie": "session=nope",
            }
        )

        async def aiter_bytes(self, chunk_size: int = 0):
            yield b"ID3fakeaudio"

        async def aclose(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def build_request(self, method: str, url: str, headers: dict[str, str] | None = None):
            captured["url"] = url
            captured["headers"] = headers or {}
            return httpx.Request(method, url, headers=headers)

        async def send(self, request: httpx.Request, stream: bool = False):
            return FakeStream()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("platform_api.services.audio_origin_proxy.httpx.AsyncClient", FakeClient)
    response = await proxy_origin_audio(
        "https://cdn1.suno.ai/ok.mp3",
        range_header="bytes=0-10",
    )
    assert captured["url"] == "https://cdn1.suno.ai/ok.mp3"
    assert captured["headers"]["Range"] == "bytes=0-10"
    assert response.status_code == 206
    header_names = {key.lower() for key in response.headers}
    assert "location" not in header_names
    assert "set-cookie" not in header_names
    assert response.headers["content-range"] == "bytes 0-10/100"
    assert "no-store" in response.headers["cache-control"]
    chunks = [chunk async for chunk in response.body_iterator]
    assert b"".join(chunks) == b"ID3fakeaudio"


@pytest.mark.asyncio
async def test_proxy_origin_audio_rejects_non_http() -> None:
    with pytest.raises(NotFoundError):
        await proxy_origin_audio("/internal/file.mp3")
