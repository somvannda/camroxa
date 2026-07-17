"""UTC datetime helpers for consistent storage and API serialization."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current instant as timezone-aware UTC."""
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC."""
    if value.tzinfo is None:
        # Legacy rows used datetime.utcnow() and were stored as local wall clock.
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_utc_iso(value: datetime | None) -> str | None:
    """Serialize a datetime as ISO-8601 UTC with a trailing Z."""
    if value is None:
        return None
    normalized = ensure_utc(value)
    return normalized.isoformat().replace("+00:00", "Z")
