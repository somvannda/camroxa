"""Signed, single-purpose tokens for browser Google OAuth and email links.

State tokens are short-lived (10 minutes) and bind the allowlisted redirect URI.
Email verification links are long-lived (24 hours) and bind the user id + email.
Both use the application JWT secret but a distinct ``type`` so they can never be
replayed as access tokens.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt

from platform_api.config import get_settings

OAUTH_STATE_TYPE = "google_oauth_state"
EMAIL_VERIFY_TYPE = "email_verify_link"

OAUTH_STATE_TTL_MINUTES = 10
EMAIL_VERIFY_TTL_HOURS = 24


def _encode(payload: dict, ttl: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    body = {
        **payload,
        "iat": now,
        "exp": now + ttl,
        "nonce": secrets.token_urlsafe(16),
    }
    return jwt.encode(body, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        return None


# ---------------------------------------------------------------------------
# Google OAuth state
# ---------------------------------------------------------------------------


def sign_oauth_state(redirect_uri: str, *, desktop_port: int | None = None) -> str:
    """Sign the OAuth state.

    ``desktop_port`` marks a native-client hand-off: Google still redirects to the
    registered https callback, then that page forwards the code to the loopback
    listener on the user's machine. The port travels inside the signed state so a
    tampered state is rejected when the desktop exchanges the code.
    """
    payload: dict = {"type": OAUTH_STATE_TYPE, "redirect_uri": redirect_uri}
    if desktop_port is not None:
        payload["desktop_port"] = int(desktop_port)
    return _encode(payload, timedelta(minutes=OAUTH_STATE_TTL_MINUTES))


def verify_oauth_state(state: str) -> str | None:
    payload = _decode(state)
    if not payload or payload.get("type") != OAUTH_STATE_TYPE:
        return None
    redirect_uri = str(payload.get("redirect_uri") or "").strip()
    return redirect_uri or None


def oauth_state_desktop_port(state: str) -> int | None:
    """Loopback port for a desktop hand-off, or None for a browser sign-in."""
    payload = _decode(state)
    if not payload or payload.get("type") != OAUTH_STATE_TYPE:
        return None
    try:
        port = int(payload.get("desktop_port"))
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


# ---------------------------------------------------------------------------
# 24-hour email verification link
# ---------------------------------------------------------------------------


def sign_email_verify_token(user_id: str, email: str) -> str:
    return _encode(
        {"type": EMAIL_VERIFY_TYPE, "sub": str(user_id), "email": email},
        timedelta(hours=EMAIL_VERIFY_TTL_HOURS),
    )


def verify_email_verify_token(token: str) -> dict | None:
    payload = _decode(token)
    if not payload or payload.get("type") != EMAIL_VERIFY_TYPE:
        return None
    if not payload.get("sub") or not payload.get("email"):
        return None
    return payload


def build_email_verify_link(user_id: str, email: str) -> str:
    settings = get_settings()
    base = (settings.music_web_base_url or "https://music.camxora.com").rstrip("/")
    token = sign_email_verify_token(user_id, email)
    return f"{base}/verify-email?token={quote(token, safe='')}"
