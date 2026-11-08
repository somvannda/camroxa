"""Regression tests: a refresh failure must not sign the user out.

Production log evidence (Nov 2026): slow / dropped ``POST /auth/refresh``
calls (17–146s, 499/502) made the desktop destroy a valid saved session and
show "Unauthenticated" on every poll until the user signed in again.
Only a server-side 401 for the refresh token itself may clear the session.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from shared.services import platform_client as platform_client_mod
from shared.services.platform_client import (
    PlatformApiError,
    PlatformClient,
    RefreshOutcome,
)

BASE = "http://test-api"


class _Storage:
    def get(self, _key: str) -> None:
        return None

    def set(self, _key: str, _value: str) -> None:
        return None

    def remove(self, _key: str) -> None:
        return None

    def get_api_base_url(self) -> str:
        return BASE


class _Response:
    def __init__(self, status_code: int, body: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.content = b""
        self.text = "" if body is None else json.dumps(body)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


def _client() -> PlatformClient:
    return PlatformClient(storage=_Storage())  # type: ignore[arg-type]


def _tokens(access: str, refresh: str = "refresh-1") -> SimpleNamespace:
    return SimpleNamespace(accessToken=access, refreshToken=refresh)


def _queue(monkeypatch: pytest.MonkeyPatch, *responses: _Response) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    remaining = list(responses)

    def _fake_request(_method: str, _url: str, **kwargs: Any) -> _Response:
        calls.append(kwargs)
        if remaining:
            return remaining.pop(0)
        return _Response(200, {})

    monkeypatch.setattr(httpx, "request", _fake_request)
    return calls


def test_transient_refresh_failure_keeps_session(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    cleared: list[bool] = []
    monkeypatch.setattr(
        client,
        "_refresh_callback",
        lambda *_a, **_k: RefreshOutcome.TRANSIENT,
    )
    client.set_session_handlers(
        get_tokens=lambda: _tokens("access-1"),
        refresh_session=client._refresh_callback,
        clear_session=lambda: cleared.append(True),
    )
    _queue(monkeypatch, _Response(401, {"detail": "Token has expired."}))

    with pytest.raises(PlatformApiError) as excinfo:
        client.request("/progress", auth=True)

    assert excinfo.value.status == 0
    assert "still saved" in str(excinfo.value)
    assert cleared == []


def test_rejected_refresh_signs_out(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    cleared: list[bool] = []
    client.set_session_handlers(
        get_tokens=lambda: _tokens("access-1"),
        refresh_session=lambda *_a, **_k: RefreshOutcome.REJECTED,
        clear_session=lambda: cleared.append(True),
    )
    _queue(monkeypatch, _Response(401, {"detail": "Token has expired."}))

    with pytest.raises(PlatformApiError) as excinfo:
        client.request("/progress", auth=True)

    assert excinfo.value.status == 401
    assert cleared == [True]


def test_legacy_false_refresh_callback_still_signs_out(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    cleared: list[bool] = []
    client.set_session_handlers(
        get_tokens=lambda: _tokens("access-1"),
        refresh_session=lambda *_a, **_k: False,
        clear_session=lambda: cleared.append(True),
    )
    _queue(monkeypatch, _Response(401, {"detail": "Token has expired."}))

    with pytest.raises(PlatformApiError) as excinfo:
        client.request("/progress", auth=True)

    assert excinfo.value.status == 401
    assert cleared == [True]


def test_successful_refresh_retries_without_sign_out(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    state = {"tokens": _tokens("access-1"), "cleared": 0}

    def _refresh(*_a: Any, **_k: Any) -> RefreshOutcome:
        state["tokens"] = _tokens("access-2", "refresh-2")
        return RefreshOutcome.REFRESHED

    client.set_session_handlers(
        get_tokens=lambda: state["tokens"],
        refresh_session=_refresh,
        clear_session=lambda: state.__setitem__("cleared", state["cleared"] + 1),
    )
    calls = _queue(
        monkeypatch,
        _Response(401, {"detail": "Token has expired."}),
        _Response(200, {"ok": True}),
    )

    assert client.request("/progress", auth=True) == {"ok": True}
    assert state["cleared"] == 0
    assert calls[-1]["headers"]["Authorization"] == "Bearer access-2"


def test_second_401_after_refresh_does_not_sign_out(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    state = {"tokens": _tokens("access-1"), "cleared": 0}

    def _refresh(*_a: Any, **_k: Any) -> RefreshOutcome:
        state["tokens"] = _tokens("access-2", "refresh-2")
        return RefreshOutcome.REFRESHED

    client.set_session_handlers(
        get_tokens=lambda: state["tokens"],
        refresh_session=_refresh,
        clear_session=lambda: state.__setitem__("cleared", state["cleared"] + 1),
    )
    _queue(
        monkeypatch,
        _Response(401, {"detail": "Token has expired."}),
        _Response(401, {"detail": "Session has been revoked."}),
    )

    with pytest.raises(PlatformApiError) as excinfo:
        client.request("/progress", auth=True)

    assert excinfo.value.status == 0
    assert state["cleared"] == 0


def test_invalidated_token_path_renews_instead_of_signing_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    state = {"tokens": _tokens("access-1"), "cleared": 0}

    def _refresh(*_a: Any, **_k: Any) -> RefreshOutcome:
        state["tokens"] = _tokens("access-2", "refresh-2")
        return RefreshOutcome.REFRESHED

    client.set_session_handlers(
        get_tokens=lambda: state["tokens"],
        refresh_session=_refresh,
        clear_session=lambda: state.__setitem__("cleared", state["cleared"] + 1),
    )
    client._invalidated_token = "access-1"
    calls = _queue(monkeypatch, _Response(200, {"ok": True}))

    assert client.request("/profiles", auth=True) == {"ok": True}
    assert state["cleared"] == 0
    assert calls[0]["headers"]["Authorization"] == "Bearer access-2"


def test_inflight_refresh_network_error_keeps_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """The keepalive timer's transient failure must leave the session alone."""
    client = _client()
    cleared: list[bool] = []

    def _refresh(*_a: Any, **_k: Any) -> RefreshOutcome:
        raise PlatformApiError(0, "Request timed out contacting the API.")

    client.set_session_handlers(
        get_tokens=lambda: _tokens("access-1"),
        refresh_session=_refresh,
        clear_session=lambda: cleared.append(True),
    )
    _queue(monkeypatch, _Response(401, {"detail": "Token has expired."}))

    with pytest.raises(PlatformApiError) as excinfo:
        client.request("/profiles", auth=True)

    assert excinfo.value.status == 0
    assert cleared == []


def test_refresh_outcome_module_message_is_user_friendly() -> None:
    assert "still saved" in platform_client_mod._TRANSIENT_REFRESH_MESSAGE
