"""Unit tests for signed OAuth state and 24-hour email activation tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from platform_api.config import get_settings
from platform_api.services.email_link_tokens import (
    OAUTH_STATE_TYPE,
    build_email_verify_link,
    sign_email_verify_token,
    sign_oauth_state,
    verify_email_verify_token,
    verify_oauth_state,
)


def test_oauth_state_roundtrip() -> None:
    state = sign_oauth_state("https://music.camxora.com/auth/callback")
    assert verify_oauth_state(state) == "https://music.camxora.com/auth/callback"


def test_oauth_state_rejects_tampering() -> None:
    state = sign_oauth_state("https://music.camxora.com/auth/callback")
    assert verify_oauth_state(state + "x") is None


def test_oauth_state_rejects_email_token() -> None:
    token = sign_email_verify_token("00000000-0000-0000-0000-000000000001", "a@example.com")
    assert verify_oauth_state(token) is None


def test_email_token_roundtrip() -> None:
    token = sign_email_verify_token("00000000-0000-0000-0000-000000000001", "a@example.com")
    payload = verify_email_verify_token(token)
    assert payload is not None
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["email"] == "a@example.com"


def test_email_token_rejects_wrong_type() -> None:
    state = sign_oauth_state("https://music.camxora.com/auth/callback")
    assert verify_email_verify_token(state) is None


def test_email_token_expires_after_24_hours() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {
            "type": "email_verify_link",
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "a@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert verify_email_verify_token(expired) is None


def test_link_points_at_music_web_verify_page() -> None:
    link = build_email_verify_link("00000000-0000-0000-0000-000000000001", "a@example.com")
    assert link.startswith("https://music.camxora.com/verify-email?token=")
    assert OAUTH_STATE_TYPE not in link
