"""Regression tests for PlatformClient.request_bytes transient-network retry.

Large binary downloads (profile logo/cover images) are the most exposed to
mid-transfer connection drops — seen in the wild as "peer closed connection
without sending complete message body (received N bytes, expected M)". GET
is idempotent, so request_bytes() retries once on a transport-level failure
(status 0) instead of surfacing a one-off network hiccup as a hard failure.
"""

from __future__ import annotations

import pytest

from shared.services import platform_client as platform_client_mod
from shared.services.platform_client import PlatformApiError, PlatformClient


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform_client_mod.time, "sleep", lambda _seconds: None)


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content


def test_request_bytes_retries_once_on_transient_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PlatformClient()
    calls = {"count": 0}

    def _fake_send(self, path, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PlatformApiError(0, "Network error: peer closed connection without sending complete message body")
        return _FakeResponse(b"full-image-bytes")

    monkeypatch.setattr(PlatformClient, "_send", _fake_send)

    result = client.request_bytes("/media/channel-profiles/p1/covers/0", auth=True)

    assert result == b"full-image-bytes"
    assert calls["count"] == 2


def test_request_bytes_does_not_retry_on_real_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PlatformClient()
    calls = {"count": 0}

    def _fake_send(self, path, **_kwargs):
        calls["count"] += 1
        raise PlatformApiError(404, "The requested item was not found.")

    monkeypatch.setattr(PlatformClient, "_send", _fake_send)

    with pytest.raises(PlatformApiError) as excinfo:
        client.request_bytes("/media/channel-profiles/p1/covers/0", auth=True)

    assert excinfo.value.status == 404
    assert calls["count"] == 1


def test_request_bytes_raises_after_exhausting_transient_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PlatformClient()
    calls = {"count": 0}

    def _fake_send(self, path, **_kwargs):
        calls["count"] += 1
        raise PlatformApiError(0, "Request timed out contacting https://api.camxora.com/api/v1.")

    monkeypatch.setattr(PlatformClient, "_send", _fake_send)

    with pytest.raises(PlatformApiError) as excinfo:
        client.request_bytes("/media/channel-profiles/p1/covers/0", auth=True)

    assert excinfo.value.status == 0
    assert calls["count"] == 2
