"""The exact Suno submit payload for custom vs description mode.

Simple mode is description-only: the idea is the whole input, so the payload
must not carry a title, lyrics or a generic style tag. Custom mode keeps its
historical ``Contemporary pop`` fallback.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from platform_api.clients.suno_client import SunoClient


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"code": 200, "data": {"taskId": "task-1"}}


class _FakeClient:
    def __init__(self, captured: dict[str, object]) -> None:
        self._captured = captured

    async def post(self, path: str, json: dict[str, object]) -> _FakeResponse:
        self._captured.clear()
        self._captured.update(json)
        self._captured["__path"] = path
        return _FakeResponse()

    async def aclose(self) -> None:
        return None


def _client(monkeypatch: pytest.MonkeyPatch, captured: dict[str, object]) -> SunoClient:
    client = SunoClient(
        SimpleNamespace(  # type: ignore[arg-type]
            suno_api_base_url="https://suno.invalid",
            suno_callback_base_url="https://api.camxora.test",
            suno_timeout_seconds=30,
        )
    )
    monkeypatch.setattr(
        SunoClient,
        "_build_client",
        lambda self, api_key: _FakeClient(captured),
    )
    return client


@pytest.mark.asyncio
async def test_description_mode_sends_no_title_lyrics_or_default_style(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    client = _client(monkeypatch, captured)

    result = await client.submit_task(
        model="V6",
        title="",
        lyrics="",
        style="",
        description="lofi workout, warm tape hiss, female vocal",
        api_key="test-key",
    )

    assert result["taskId"] == "task-1"
    assert captured["customMode"] is False
    assert captured["gpt_description_prompt"] == "lofi workout, warm tape hiss, female vocal"
    assert "style" not in captured
    assert "title" not in captured
    assert "prompt" not in captured


@pytest.mark.asyncio
async def test_description_mode_forwards_an_explicit_style(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    client = _client(monkeypatch, captured)

    await client.submit_task(
        model="V6",
        title="",
        lyrics="",
        style="synthwave",
        description="night drive",
        api_key="test-key",
    )

    assert captured["style"] == "synthwave"


@pytest.mark.asyncio
async def test_custom_mode_keeps_the_style_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    client = _client(monkeypatch, captured)

    await client.submit_task(
        model="V6",
        title="A Title",
        lyrics="[Verse]\nline",
        style="",
        api_key="test-key",
    )

    assert captured["customMode"] is True
    assert captured["style"] == "Contemporary pop"
    assert captured["title"] == "A Title"
    assert captured["prompt"] == "[Verse]\nline"
