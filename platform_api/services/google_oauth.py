"""Google OAuth helpers for music-web sign-in.

Reuses the same Google Cloud OAuth client as ``musicapi.camxora.com``. The
browser performs the consent redirect; this module builds the URL, validates the
signed state, exchanges the authorization code, and verifies the ``id_token``.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from platform_api.config import get_settings
from platform_api.exceptions import AuthenticationError

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email profile"


def redirect_allowlist() -> list[str]:
    raw = get_settings().google_redirect_uris or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def google_configured() -> bool:
    settings = get_settings()
    return bool(
        (settings.google_client_id or "").strip()
        and (settings.google_client_secret or "").strip()
    )


def resolve_redirect_uri(requested: str | None) -> str:
    allowlist = redirect_allowlist()
    if not allowlist:
        raise AuthenticationError("Google sign-in is not configured.")
    candidate = (requested or "").strip()
    if candidate and candidate in allowlist:
        return candidate
    return allowlist[0]


def authorization_url(redirect_uri: str, state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code and return verified Google profile data."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
    if response.status_code != 200:
        raise AuthenticationError("Google sign-in failed. Please try again.")
    payload = response.json()
    id_token = payload.get("id_token")
    if not id_token:
        raise AuthenticationError("Google did not return an identity token.")

    try:
        info = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:  # includes expired / wrong-audience tokens
        raise AuthenticationError("Google identity token is invalid.") from exc

    if not info.get("sub") or not info.get("email"):
        raise AuthenticationError("Google did not return a valid profile.")
    if info.get("email_verified") is not True:
        raise AuthenticationError("Your Google account email is not verified.")
    return info
