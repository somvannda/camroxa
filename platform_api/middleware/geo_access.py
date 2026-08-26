"""Cambodia-only geo gate for music web.

Uses Cloudflare ``CF-IPCountry`` (never a client-spoofable body field).
Fail closed when Cloudflare is in the path: missing, unknown (XX), Tor (T1), or
any country other than KH is blocked. Direct origin (no CF headers, e.g. sandbox
DNS-only) is not geo-gated so local/sandbox traffic keeps working.

Scope:
  - Host is music.camxora.com / music.sandbox.camxora.com, or
  - Path is /api/v3/web-music/* (blocks bypass via api.camxora.com)

Not applied to /health or /callbacks. Desktop /generation and admin stay open.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from platform_api.config import get_settings, is_music_web_geo_enforced
from platform_api.exceptions import GeoBlockedError

logger = logging.getLogger(__name__)

MUSIC_WEB_HOSTS = frozenset(
    {
        "music.camxora.com",
        "music.sandbox.camxora.com",
    }
)
BLOCKED_COUNTRY_CODES = frozenset({"", "XX", "T1", "A1"})
GEO_MESSAGE = "This service is only available in Cambodia."


def request_host(request: Request) -> str:
    raw = (request.headers.get("host") or "").split(":")[0].strip().lower()
    return raw


def request_path(request: Request) -> str:
    return str(request.url.path or "").lower()


def is_geo_exempt_path(path: str) -> bool:
    normalized = path.lower()
    if normalized in {"/health", "/api/v3/health"} or normalized.startswith("/health"):
        return True
    if "/callbacks" in normalized:
        return True
    return False


def music_web_geo_in_scope(request: Request) -> bool:
    """Return True when this request must pass the KH-only check."""
    path = request_path(request)
    if is_geo_exempt_path(path):
        return False
    if request_host(request) in MUSIC_WEB_HOSTS:
        return True
    if path.startswith("/api/v3/web-music") or path.startswith("/web-music"):
        return True
    if path.startswith("/api/v3/public/streaming"):
        return True
    return False


def client_ip(request: Request) -> str:
    """Prefer Cloudflare connecting IP, then X-Forwarded-For, then socket."""
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def cloudflare_seen(request: Request) -> bool:
    """True when the request actually came through Cloudflare."""
    if (request.headers.get("cf-connecting-ip") or "").strip():
        return True
    if (request.headers.get("cf-ray") or "").strip():
        return True
    if (request.headers.get("cf-ipcountry") or "").strip():
        return True
    return False


def country_from_request(request: Request) -> str:
    """Cloudflare country code. Empty when the header is missing."""
    return (request.headers.get("cf-ipcountry") or "").strip().upper()


def allowed_country_code() -> str:
    settings = get_settings()
    return (settings.music_web_geo_allowed_country or "KH").strip().upper() or "KH"


def geo_is_allowed(country: str, *, allowed: str | None = None) -> bool:
    expected = (allowed or allowed_country_code()).strip().upper()
    code = (country or "").strip().upper()
    if code in BLOCKED_COUNTRY_CODES:
        return False
    return code == expected


def geo_blocked_response(*, country: str) -> JSONResponse:
    payload = {
        "error": {
            "code": GeoBlockedError.error_code,
            "message": GEO_MESSAGE,
            "details": {"country": country or None},
        }
    }
    return JSONResponse(status_code=403, content=payload)


class MusicWebGeoMiddleware:
    """Fail-closed KH-only gate for music web hosts and /web-music paths.

    Pure ASGI (not BaseHTTPMiddleware) so Range audio streams are not buffered
    and cookies stay on the original request.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not is_music_web_geo_enforced():
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if not music_web_geo_in_scope(request):
            await self.app(scope, receive, send)
            return

        # Sandbox (and any origin not behind Cloudflare) has no CF-IPCountry.
        # Fail closed only when Cloudflare is actually in the path.
        if not cloudflare_seen(request):
            await self.app(scope, receive, send)
            return

        country = country_from_request(request)
        if geo_is_allowed(country):
            await self.app(scope, receive, send)
            return

        logger.warning(
            "Music web geo blocked host=%s path=%s country=%s ip=%s",
            request_host(request),
            request_path(request),
            country or "missing",
            client_ip(request),
        )
        await geo_blocked_response(country=country)(scope, receive, send)
