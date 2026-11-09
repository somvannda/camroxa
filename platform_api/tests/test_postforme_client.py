"""Post for Me client request shaping and retry tests."""

from __future__ import annotations

import httpx
import pytest

from platform_api.exceptions import ExternalServiceError
from platform_api.services.postforme_client import PostForMeClient


def _client(handler) -> PostForMeClient:
    return PostForMeClient(
        api_key="pfm_test_key",
        base_url="https://api.postforme.dev/v1",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_media_upload_uses_bearer_auth_and_returns_urls() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization", "")
        return httpx.Response(
            200,
            json={"upload_url": "https://storage.example/put", "media_url": "https://cdn.example/v.mp4"},
        )

    result = await _client(handler).create_media_upload_url()

    assert seen["url"] == "https://api.postforme.dev/v1/media/create-upload-url"
    assert seen["auth"] == "Bearer pfm_test_key"
    assert result["media_url"] == "https://cdn.example/v.mp4"


@pytest.mark.asyncio
async def test_rate_limit_retries_after_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("platform_api.services.postforme_client.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "slow down"})
        return httpx.Response(
            200,
            json={"upload_url": "https://storage.example/put", "media_url": "https://cdn.example/v.mp4"},
        )

    result = await _client(handler).create_media_upload_url()

    assert calls["count"] == 2
    assert result["upload_url"] == "https://storage.example/put"


@pytest.mark.asyncio
async def test_client_error_is_not_retried() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"error": "invalid account"})

    with pytest.raises(ExternalServiceError) as excinfo:
        await _client(handler).create_social_post({"caption": "x", "social_accounts": ["spc_1"]})

    assert calls["count"] == 1
    assert "invalid account" in str(excinfo.value)
    assert excinfo.value.is_retryable is False


@pytest.mark.asyncio
async def test_missing_api_key_fails_closed() -> None:
    client = PostForMeClient(api_key="", base_url="https://api.postforme.dev/v1")
    with pytest.raises(ExternalServiceError) as excinfo:
        await client.create_media_upload_url()
    assert excinfo.value.is_retryable is False


@pytest.mark.asyncio
async def test_list_results_reads_data_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("post_id") == "post_1"
        return httpx.Response(
            200,
            json={"data": [{"id": "res_1", "success": True}], "meta": {"total": 1}},
        )

    results = await _client(handler).list_social_post_results("post_1")
    assert results == [{"id": "res_1", "success": True}]
