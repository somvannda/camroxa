"""Build WebSocket URLs for platform_api push notifications."""

from __future__ import annotations


def build_platform_ws_url(api_base_url: str, access_token: str | None = None) -> str:
    """Convert REST base URL to /api/v3/ws URL.

    Authenticate with the ``Authorization`` header at connect time
    (``build_platform_ws_auth_headers``) — never in the query string, which
    leaks the token into proxy/server access logs. ``access_token`` is accepted
    for backward compatibility but ignored.
    """
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("API base URL is required.")

    if base.endswith("/api/v3"):
        rest_prefix = base
    else:
        rest_prefix = f"{base}/api/v3"

    ws_prefix = rest_prefix.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_prefix}/ws"


def build_platform_ws_auth_headers(access_token: str) -> dict[str, str]:
    token = str(access_token or "").strip()
    if not token:
        raise ValueError("Access token is required.")
    return {"Authorization": f"Bearer {token}"}
