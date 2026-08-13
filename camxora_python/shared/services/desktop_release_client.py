"""Public desktop-release fetch (no auth) for startup force-update checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

DesktopReleaseFetchStatus = Literal["ok", "not_found", "unreachable"]


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


@dataclass(slots=True, frozen=True)
class DesktopReleaseFetchResult:
    """Outcome of a public desktop-release lookup.

    ``ok`` — server returned a published release.
    ``not_found`` — confirmed no live release (404). Treat as withdrawn.
    ``unreachable`` — network/5xx/invalid payload. Do not assume withdrawal.
    """

    status: DesktopReleaseFetchStatus
    release: PublishedDesktopRelease | None = None

    @property
    def withdrawn(self) -> bool:
        return self.status == "not_found"


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
    return fetch_published_desktop_release_result(api_base_url, timeout=timeout).release


def fetch_published_desktop_release_result(
    api_base_url: str,
    *,
    timeout: float = 8.0,
) -> DesktopReleaseFetchResult:
    """Fetch live release and distinguish 404 (withdrawn) from network failure."""
    try:
        url = desktop_release_url_for_api_base(api_base_url)
    except ValueError:
        return DesktopReleaseFetchResult(status="unreachable")

    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError:
        return DesktopReleaseFetchResult(status="unreachable")

    if response.status_code == 404:
        return DesktopReleaseFetchResult(status="not_found")
    if not response.is_success:
        return DesktopReleaseFetchResult(status="unreachable")

    try:
        payload = response.json()
    except ValueError:
        return DesktopReleaseFetchResult(status="unreachable")
    if not isinstance(payload, dict):
        return DesktopReleaseFetchResult(status="unreachable")

    version = str(payload.get("version") or "").strip()
    if not version:
        return DesktopReleaseFetchResult(status="unreachable")

    return DesktopReleaseFetchResult(
        status="ok",
        release=PublishedDesktopRelease(
            version=version,
            download_url=str(payload.get("download_url") or "").strip(),
            release_notes=str(payload.get("release_notes") or "").strip(),
            mandatory=bool(payload.get("mandatory")),
            published_at=str(payload.get("published_at") or "").strip(),
        ),
    )
