"""Per-request active upstream host for the Suno-compatible provider.

``platform_api`` can talk to more than one Suno-compatible reseller
(sunoapi.org / apibox and Camxora's own ``musicapi``). Key selection resolves
which host a request should use and publishes it here, so the HTTP client can
pick the right base URL without threading the value through every call
signature.

The value is a :class:`contextvars.ContextVar`, so concurrent requests never see
each other's host.
"""

from __future__ import annotations

from contextvars import ContextVar

_active_suno_base_url: ContextVar[str] = ContextVar("active_suno_base_url", default="")


def set_active_suno_base_url(url: str | None) -> None:
    """Publish the upstream base URL for the current request/task."""
    _active_suno_base_url.set(str(url or "").rstrip("/"))


def get_active_suno_base_url(default: str = "") -> str:
    """Return the current request's upstream base URL, or ``default``."""
    return _active_suno_base_url.get() or str(default or "").rstrip("/")


__all__ = ["set_active_suno_base_url", "get_active_suno_base_url"]
