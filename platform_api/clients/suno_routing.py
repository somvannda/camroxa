"""Per-request active upstream host for the Suno-compatible provider.

Both Suno-compatible provider ids (``suno`` and ``camxora_music_api``) now
resolve to Camxora's own ``musicapi``; the split exists only so AI Routing can
price them differently. Key selection resolves which host a request should use
and publishes it here, so the HTTP client can pick the right base URL without
threading the value through every call signature.

The value is a :class:`contextvars.ContextVar`, so concurrent requests never see
each other's host.
"""

from __future__ import annotations

from contextvars import ContextVar

#: Providers that speak the Suno-compatible HTTP contract through the shared
#: Suno client. Both target Camxora's own ``musicapi.camxora.com``; the ids are
#: kept separate only for AI Routing credit pricing.
SUNO_COMPATIBLE_PROVIDERS: frozenset[str] = frozenset({"suno", "camxora_music_api"})

#: Music provider used when AI Routing has no explicit assignment.
DEFAULT_MUSIC_PROVIDER = "suno"

_active_suno_base_url: ContextVar[str] = ContextVar("active_suno_base_url", default="")


def is_suno_compatible_provider(provider: str | None) -> bool:
    """True when ``provider`` is served by the shared Suno-compatible client."""
    return str(provider or "").strip().lower() in SUNO_COMPATIBLE_PROVIDERS


def normalize_music_provider(provider: str | None) -> str:
    """Return a valid music routing provider id, defaulting to ``suno``."""
    value = str(provider or "").strip().lower()
    return value if value in SUNO_COMPATIBLE_PROVIDERS else DEFAULT_MUSIC_PROVIDER


def set_active_suno_base_url(url: str | None) -> None:
    """Publish the upstream base URL for the current request/task."""
    _active_suno_base_url.set(str(url or "").rstrip("/"))


def get_active_suno_base_url(default: str = "") -> str:
    """Return the current request's upstream base URL, or ``default``."""
    return _active_suno_base_url.get() or str(default or "").rstrip("/")


__all__ = [
    "DEFAULT_MUSIC_PROVIDER",
    "SUNO_COMPATIBLE_PROVIDERS",
    "get_active_suno_base_url",
    "is_suno_compatible_provider",
    "normalize_music_provider",
    "set_active_suno_base_url",
]
