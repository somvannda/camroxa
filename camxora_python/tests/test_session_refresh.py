"""Tests for concurrent session refresh behavior."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from shared.models.auth import AuthTokens, TokenResponse
from shared.services.session_service import SessionService


def _store_tokens(session: SessionService, *, access: str, refresh: str, expires_in_s: int = 3600) -> None:
    expires_at = int(time.time() * 1000) + expires_in_s * 1000
    tokens = AuthTokens(
        accessToken=access,
        refreshToken=refresh,
        tokenType="bearer",
        expiresAt=expires_at,
    )
    session.set_tokens(tokens)


def test_ensure_fresh_session_dedupes_parallel_refresh() -> None:
    session = SessionService()
    _store_tokens(session, access="access-1", refresh="refresh-1", expires_in_s=10)

    refresh_calls: list[str] = []
    lock = threading.Lock()

    def _refresh(refresh_token: str) -> TokenResponse:
        with lock:
            refresh_calls.append(refresh_token)
        time.sleep(0.05)
        return TokenResponse(
            access_token="access-2",
            refresh_token="refresh-2",
            token_type="bearer",
            expires_in=3600,
        )

    session._api.refresh = MagicMock(side_effect=_refresh)  # type: ignore[method-assign]

    results: list[bool] = []

    def _worker() -> None:
        results.append(session.ensure_fresh_session(force=True))

    threads = [threading.Thread(target=_worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(results)
    assert refresh_calls == ["refresh-1"]
    assert session.get_tokens() is not None
    assert session.get_tokens().refreshToken == "refresh-2"


def test_ensure_fresh_session_skips_second_forced_refresh_after_renewal() -> None:
    session = SessionService()
    _store_tokens(session, access="access-1", refresh="refresh-1", expires_in_s=3600)

    session._api.refresh = MagicMock(  # type: ignore[method-assign]
        return_value=TokenResponse(
            access_token="access-2",
            refresh_token="refresh-2",
            token_type="bearer",
            expires_in=3600,
        )
    )

    assert session.ensure_fresh_session(force=True) is True
    assert session._api.refresh.call_count == 0

    _store_tokens(session, access="access-old", refresh="refresh-old", expires_in_s=5)
    assert session.ensure_fresh_session(force=True) is True
    assert session._api.refresh.call_count == 1

    assert session.ensure_fresh_session(force=True) is True
    assert session._api.refresh.call_count == 1


def test_ensure_fresh_session_rotates_when_access_token_got_401() -> None:
    session = SessionService()
    _store_tokens(session, access="access-1", refresh="refresh-1", expires_in_s=3600)
    session._api.refresh = MagicMock(  # type: ignore[method-assign]
        return_value=TokenResponse(
            access_token="access-2",
            refresh_token="refresh-2",
            token_type="bearer",
            expires_in=3600,
        )
    )

    assert session.ensure_fresh_session(force=True, failed_access_token="access-1") is True
    assert session._api.refresh.call_count == 1
    assert session.get_tokens().accessToken == "access-2"

    assert session.ensure_fresh_session(force=True, failed_access_token="access-1") is True
    assert session._api.refresh.call_count == 1
