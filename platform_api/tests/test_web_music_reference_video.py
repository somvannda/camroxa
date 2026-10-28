"""Suno create-composer reference video parity.

Suno's `+ → Video` attaches exactly one reference clip and sends it as
`user_uploaded_video_id`. Camxora stores the uploaded URL and forwards it to
musicapi as `videoUrls`; these tests pin that contract.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from platform_api.clients.suno_client import SunoClient
from platform_api.ports.generation_port import SunoRequest
from platform_api.routers.web_music import WebMusicGenerateRequest


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        suno_api_base_url="https://musicapi.example.test",
        suno_callback_base_url="https://platform.example.test",
        suno_timeout_seconds=10.0,
    )


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


class _FakeClient:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def post(self, _url: str, *, json: dict) -> _FakeResponse:
        self.payloads.append(json)
        return _FakeResponse({"code": 200, "data": {"taskId": "clip-1"}})

    async def aclose(self) -> None:
        return None


def test_suno_request_defaults_to_no_reference_video() -> None:
    request = SunoRequest(model="V6", title="T", lyrics="L", style="pop")

    assert request.video_urls == []


def test_generate_request_accepts_one_video_url() -> None:
    body = WebMusicGenerateRequest(prompt="a song", video_urls=["https://cdn.test/a.mp4"])

    assert body.video_urls == ["https://cdn.test/a.mp4"]


def test_generate_request_rejects_two_video_urls() -> None:
    with pytest.raises(ValidationError):
        WebMusicGenerateRequest(
            prompt="a song",
            video_urls=["https://cdn.test/a.mp4", "https://cdn.test/b.webm"],
        )


@pytest.mark.asyncio
async def test_submit_task_forwards_only_one_video_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SunoClient(_settings())  # type: ignore[arg-type]
    fake = _FakeClient()
    monkeypatch.setattr(client, "_build_client", lambda _api_key: fake)

    await client.submit_task(
        model="V6",
        title="Song",
        lyrics="Verse",
        style="pop",
        instrumental=False,
        api_key="key",
        video_urls=["https://cdn.test/a.mp4", "https://cdn.test/b.webm"],
    )

    assert fake.payloads[0]["videoUrls"] == ["https://cdn.test/a.mp4"]


@pytest.mark.asyncio
async def test_submit_task_omits_video_urls_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SunoClient(_settings())  # type: ignore[arg-type]
    fake = _FakeClient()
    monkeypatch.setattr(client, "_build_client", lambda _api_key: fake)

    await client.submit_task(
        model="V6",
        title="Song",
        lyrics="Verse",
        style="pop",
        instrumental=False,
        api_key="key",
    )

    assert "videoUrls" not in fake.payloads[0]
