"""Session refresh outcome tests: transient failures never sign the user out."""

from __future__ import annotations

import time

import pytest

from shared.models.auth import AuthTokens, TokenResponse
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError, PlatformClient, RefreshOutcome
from shared.services.secure_storage import TOKENS_STORAGE_KEY
from shared.services.session_service import SessionService


class _MemoryStorage:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value

    def remove(self, key: str) -> None:
        self.data.pop(key, None)

    def reload(self) -> bool:
        return True

    def get_api_base_url(self) -> str:
        return "http://test-api"


def _session() -> tuple[SessionService, _MemoryStorage]:
    storage = _MemoryStorage()
    api = PlatformApi(PlatformClient(storage=storage))  # type: ignore[arg-type]
    return SessionService(storage=storage, api=api), storage  # type: ignore[arg-type]


def _store(session: SessionService, *, access: str, refresh: str, expires_in_s: int = 10) -> None:
    session.set_tokens(
        AuthTokens(
            accessToken=access,
            refreshToken=refresh,
            tokenType="bearer",
            expiresAt=int(time.time() * 1000) + expires_in_s * 1000,
        )
    )


def _new_pair(access: str, refresh: str) -> TokenResponse:
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=3600,
    )


def test_transient_refresh_failure_keeps_saved_session() -> None:
    session, _ = _session()
    _store(session, access="access-1", refresh="refresh-1")
    session._api.refresh = lambda _token: (_ for _ in ()).throw(  # type: ignore[method-assign]
        PlatformApiError(0, "Request timed out contacting the API.")
    )

    outcome = session.refresh_session(force=True)

    assert outcome is RefreshOutcome.TRANSIENT
    tokens = session.get_tokens()
    assert tokens is not None
    assert tokens.refreshToken == "refresh-1"
    assert session.ensure_fresh_session(force=True) is False


def test_server_rejection_clears_session() -> None:
    session, _ = _session()
    _store(session, access="access-1", refresh="refresh-1")
    session._api.refresh = lambda _token: (_ for _ in ()).throw(  # type: ignore[method-assign]
        PlatformApiError(401, "This session has already been refreshed. Please sign in again.")
    )

    outcome = session.refresh_session(force=True)

    assert outcome is RefreshOutcome.REJECTED
    assert session.get_tokens() is None


def test_rotated_pair_from_another_instance_is_adopted() -> None:
    session, storage = _session()
    _store(session, access="access-1", refresh="refresh-1")

    # A second studio window rotated the token pair and saved it.
    newer = AuthTokens(
        accessToken="access-2",
        refreshToken="refresh-2",
        tokenType="bearer",
        expiresAt=int(time.time() * 1000) + 3_600_000,
    )
    storage.data[TOKENS_STORAGE_KEY] = newer.model_dump_json()

    session._api.refresh = lambda _token: (_ for _ in ()).throw(  # type: ignore[method-assign]
        PlatformApiError(401, "This session has already been refreshed. Please sign in again.")
    )

    outcome = session.refresh_session(force=True, failed_access_token="access-1")

    assert outcome is RefreshOutcome.NOT_NEEDED
    tokens = session.get_tokens()
    assert tokens is not None
    assert tokens.accessToken == "access-2"
    assert tokens.refreshToken == "refresh-2"


def test_successful_refresh_reports_refreshed() -> None:
    session, _ = _session()
    _store(session, access="access-1", refresh="refresh-1")
    session._api.refresh = lambda _token: _new_pair("access-2", "refresh-2")  # type: ignore[method-assign]

    assert session.refresh_session(force=True) is RefreshOutcome.REFRESHED
    assert session.get_tokens() is not None
    assert session.get_tokens().refreshToken == "refresh-2"
    assert session.ensure_fresh_session(force=True) is True


@pytest.mark.parametrize("status", [0, 429, 500, 502, 503])
def test_retryable_http_statuses_are_transient(status: int) -> None:
    session, _ = _session()
    _store(session, access="access-1", refresh="refresh-1")
    session._api.refresh = lambda _token: (_ for _ in ()).throw(  # type: ignore[method-assign]
        PlatformApiError(status, "temporarily unavailable")
    )

    assert session.refresh_session(force=True) is RefreshOutcome.TRANSIENT
    assert session.get_tokens() is not None


def test_bootstrap_keeps_session_when_refresh_hits_network_error() -> None:
    session, _ = _session()
    _store(session, access="access-1", refresh="refresh-1", expires_in_s=-10)
    session._api.refresh = lambda _token: (_ for _ in ()).throw(  # type: ignore[method-assign]
        PlatformApiError(0, "Request timed out contacting the API.")
    )

    result = session.run_bootstrap()

    assert result.destination.value == "login"
    assert "still saved" in result.message or "sign-in is saved" in result.message
    tokens = session.get_tokens()
    assert tokens is not None
    assert tokens.refreshToken == "refresh-1"


def test_bootstrap_keeps_session_when_get_me_is_unreachable() -> None:
    session, _ = _session()
    _store(session, access="access-1", refresh="refresh-1", expires_in_s=3600)
    session._api.get_me = lambda: (_ for _ in ()).throw(  # type: ignore[method-assign]
        PlatformApiError(0, "Cannot reach Camxora servers.")
    )

    result = session.run_bootstrap()

    assert result.destination.value == "login"
    assert "sign-in is saved" in result.message
    assert session.get_tokens() is not None
