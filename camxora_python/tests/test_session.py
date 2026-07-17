"""Tests for session token parsing."""

import json

from shared.models.auth import AuthTokens, TokenResponse
from shared.services.session_service import _parse_tokens


def test_tokens_from_response() -> None:
    tokens = AuthTokens.from_token_response(
        TokenResponse(
            access_token="access",
            refresh_token="refresh",
            token_type="bearer",
            expires_in=3600,
        )
    )
    assert tokens.accessToken == "access"
    assert tokens.refreshToken == "refresh"
    assert tokens.expiresAt > 0


def test_parse_tokens_valid() -> None:
    payload = json.dumps(
        {
            "accessToken": "a",
            "refreshToken": "r",
            "tokenType": "bearer",
            "expiresAt": 9999999999999,
        }
    )
    tokens = _parse_tokens(payload)
    assert tokens is not None
    assert tokens.accessToken == "a"


def test_parse_tokens_invalid() -> None:
    assert _parse_tokens(None) is None
    assert _parse_tokens("{bad") is None
