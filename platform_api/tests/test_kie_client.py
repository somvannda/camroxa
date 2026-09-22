"""Unit tests for the kie.ai Market API client (Grok Imagine text-to-image)."""

from __future__ import annotations

import httpx
import pytest

from platform_api.clients.kie_client import (
    KieClient,
    _aspect_ratio,
)
from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError


def _settings() -> Settings:
    return Settings(kie_api_base_url="https://kie.example.com")


class _Resp:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "https://kie.example.com"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> object:
        return self._payload


class _FakeClient:
    """Fake httpx.AsyncClient returning queued post/get responses."""

    def __init__(self, post_responses, get_responses, **_kwargs) -> None:
        self._post_responses = list(post_responses)
        self._get_responses = list(get_responses)
        self.calls: list[tuple[str, str, dict]] = []

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def post(self, url: str, json: dict | None = None) -> _Resp:
        self.calls.append(("POST", url, json or {}))
        return self._post_responses.pop(0)

    async def get(self, url: str, params: dict | None = None) -> _Resp:
        self.calls.append(("GET", url, params or {}))
        return self._get_responses.pop(0)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_aspect_ratio_mapping() -> None:
    assert _aspect_ratio(1024, 1024) == "1:1"
    assert _aspect_ratio(1920, 1080) == "16:9"
    assert _aspect_ratio(1080, 1920) == "9:16"
    assert _aspect_ratio(1536, 1024) == "3:2"
    assert _aspect_ratio(1024, 1536) == "2:3"
    # Unknown / zero dimensions fall back to square.
    assert _aspect_ratio(0, 0) == "1:1"


def test_normalize_success_parses_result_json_string() -> None:
    payload = {
        "taskId": "task_1",
        "state": "success",
        "resultJson": '{"resultUrls":["https://cdn.example.com/a.jpg"]}',
    }
    result = KieClient._normalize_success(payload, task_id="task_1")
    assert result == {"data": [{"url": "https://cdn.example.com/a.jpg"}]}


def test_normalize_success_accepts_dict_result_json() -> None:
    payload = {
        "taskId": "task_2",
        "state": "success",
        "resultJson": {"resultUrls": ["https://cdn.example.com/b.jpg"]},
    }
    result = KieClient._normalize_success(payload, task_id="task_2")
    assert result["data"][0]["url"] == "https://cdn.example.com/b.jpg"


def test_normalize_success_without_urls_raises() -> None:
    with pytest.raises(ExternalServiceError):
        KieClient._normalize_success(
            {"taskId": "t", "state": "success", "resultJson": "{}"},
            task_id="t",
        )


def test_raise_for_body_code_billing_is_not_retryable() -> None:
    """402/403 must surface as a non-retryable ExternalServiceError.

    It must NOT be an httpx.HTTPStatusError, otherwise the key pool would
    mark the key exhausted (matching the Suno/SLAI behavior).
    """
    for code in (402, 403):
        with pytest.raises(ExternalServiceError) as exc:
            KieClient._raise_for_body_code(
                {"code": code, "msg": "no credits"}, url="https://kie.example.com"
            )
        assert exc.value.is_retryable is False
        assert not isinstance(exc.value, httpx.HTTPStatusError)
        assert exc.value.details.get("status_code") == code


def test_raise_for_body_code_rate_limit_is_retryable() -> None:
    for code in (429, 433):
        with pytest.raises(ExternalServiceError) as exc:
            KieClient._raise_for_body_code(
                {"code": code, "msg": "slow down"}, url="https://kie.example.com"
            )
        assert exc.value.is_retryable is True
        assert not isinstance(exc.value, httpx.HTTPStatusError)


def test_raise_for_body_code_server_error_is_retryable() -> None:
    with pytest.raises(ExternalServiceError) as exc:
        KieClient._raise_for_body_code(
            {"code": 500, "msg": "boom"}, url="https://kie.example.com"
        )
    assert exc.value.is_retryable is True


def test_raise_for_body_code_success_is_noop() -> None:
    KieClient._raise_for_body_code({"code": 200, "msg": "success"}, url="https://x")


# ---------------------------------------------------------------------------
# generate_image flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_image_submits_and_returns_url(monkeypatch) -> None:
    import platform_api.clients.kie_client as mod

    post_resp = _Resp({"code": 200, "msg": "success", "data": {"taskId": "task_abc"}})
    poll_resp = _Resp(
        {
            "code": 200,
            "msg": "success",
            "data": {
                "taskId": "task_abc",
                "state": "success",
                "resultJson": '{"resultUrls":["https://cdn.example.com/out.jpg"]}',
            },
        }
    )
    monkeypatch.setattr(
        mod.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient([post_resp], [poll_resp], **kwargs),
    )

    client = KieClient(_settings())
    client._poll_interval = 0.0
    result = await client.generate_image(prompt="a cat", width=1920, height=1080, api_key="k")

    assert result["data"][0]["url"] == "https://cdn.example.com/out.jpg"


@pytest.mark.asyncio
async def test_generate_image_surfaces_failure_state(monkeypatch) -> None:
    import platform_api.clients.kie_client as mod

    post_resp = _Resp({"code": 200, "msg": "success", "data": {"taskId": "task_bad"}})
    poll_resp = _Resp(
        {
            "code": 200,
            "msg": "success",
            "data": {"taskId": "task_bad", "state": "fail", "failMsg": "policy violation"},
        }
    )
    monkeypatch.setattr(
        mod.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient([post_resp], [poll_resp], **kwargs),
    )

    client = KieClient(_settings())
    client._poll_interval = 0.0
    with pytest.raises(ExternalServiceError) as exc:
        await client.generate_image(prompt="x", api_key="k")
    assert exc.value.is_retryable is False


@pytest.mark.asyncio
async def test_generate_image_requires_api_key() -> None:
    client = KieClient(_settings())
    with pytest.raises(ExternalServiceError):
        await client.generate_image(prompt="x", api_key=None)


@pytest.mark.asyncio
async def test_generate_image_http_402_is_external_and_not_retryable(monkeypatch) -> None:
    """HTTP-level 402 must not escape as httpx.HTTPStatusError (no key exhaustion)."""
    import platform_api.clients.kie_client as mod

    post_resp = _Resp({"code": 402, "msg": "no credits"}, status_code=402)
    monkeypatch.setattr(
        mod.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient([post_resp], [], **kwargs),
    )

    client = KieClient(_settings())
    with pytest.raises(ExternalServiceError) as exc:
        await client.generate_image(prompt="x", api_key="k")
    assert not isinstance(exc.value, httpx.HTTPStatusError)
    assert exc.value.is_retryable is False
    assert exc.value.details.get("status_code") == 402
