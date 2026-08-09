"""Public desktop-release fetch (no auth) for startup force-update checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True, frozen=True)
class PublishedDesktopRelease:
    version: str
    download_url: str
    release_notes: str
    mandatory: bool
    published_at: str = ""

    def as_update_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "download_url": self.download_url,
            "release_notes": self.release_notes,
            "mandatory": self.mandatory,
            "notification_id": "startup-desktop-release",
        }


def desktop_release_url_for_api_base(api_base_url: str) -> str:
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("API base URL is required")
    return f"{base}/public/desktop-release"


def fetch_published_desktop_release(
    api_base_url: str,
    *,
    timeout: float = 8.0,
) -> PublishedDesktopRelease | None:
    """Return the published release, or None if none / unreachable (fail-open)."""
    try:
        url = desktop_release_url_for_api_base(api_base_url)
    except ValueError:
        return None

    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError:
        return None

    if response.status_code == 404:
        return None
    if not response.is_success:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    version = str(payload.get("version") or "").strip()
    if not version:
        return None

    return PublishedDesktopRelease(
        version=version,
        download_url=str(payload.get("download_url") or "").strip(),
        release_notes=str(payload.get("release_notes") or "").strip(),
        mandatory=bool(payload.get("mandatory")),
        published_at=str(payload.get("published_at") or "").strip(),
    )
