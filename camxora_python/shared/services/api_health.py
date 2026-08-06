"""Platform API health check utilities."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from shared.services.build_config import is_api_url_locked
from shared.services.secure_storage import DEFAULT_API_BASE_URL


def health_url_for_api_base(api_base_url: str) -> str:
    """Build the root /health URL from an /api/v1 base URL."""
    parsed = urlparse(api_base_url.rstrip("/"))
    if parsed.path.endswith("/api/v1"):
        root = api_base_url[: -len("/api/v1")]
    else:
        root = f"{parsed.scheme}://{parsed.netloc}"
    return f"{root.rstrip('/')}/health"


def _unreachable_message(api_base_url: str) -> str:
    base = str(api_base_url or "").strip() or "the Camxora API"
    if is_api_url_locked():
        return (
            f"Cannot reach Camxora servers ({base}). "
            "Check your internet connection and try again."
        )
    return f"Cannot connect to {base}. Start platform_api on port 8000."


def check_api_reachable(api_base_url: str = DEFAULT_API_BASE_URL, timeout: float = 3.0) -> tuple[bool, str]:
    """Return whether platform_api responds and a short status message."""
    health_url = health_url_for_api_base(api_base_url)
    try:
        response = httpx.get(health_url, timeout=timeout)
        if response.is_success:
            return True, f"API connected: {api_base_url}"
        return False, f"API returned HTTP {response.status_code} at {health_url}"
    except httpx.ConnectError:
        return False, _unreachable_message(api_base_url)
    except httpx.TimeoutException:
        return False, f"API timed out at {health_url}"
    except httpx.HTTPError as exc:
        return False, f"API error: {exc}"
