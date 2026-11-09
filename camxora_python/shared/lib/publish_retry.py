"""Retry policy for publishing (transient provider/network failures only)."""

from __future__ import annotations

MAX_ATTEMPTS = 3
BACKOFF_SECONDS: tuple[float, ...] = (2.0, 6.0)

_TRANSIENT_HINTS = (
    "timeout",
    "timed out",
    "connection",
    "temporarily",
    "try again",
    "unavailable",
    "502",
    "503",
    "504",
)


def should_retry(status: int | None, message: str | None = None) -> bool:
    """True for transport-level or 5xx failures; never for 4xx/auth/validation."""
    if status is None or status == 0:
        return True
    if status >= 500:
        return True
    if status == 429:
        return True
    if status in (400, 401, 403, 404, 409, 422):
        return False
    text = str(message or "").lower()
    return any(hint in text for hint in _TRANSIENT_HINTS)


def backoff_for(attempt: int) -> float:
    """Seconds to wait before attempt N+1 (attempt is 1-based)."""
    if attempt <= 0:
        return 0.0
    index = min(attempt - 1, len(BACKOFF_SECONDS) - 1)
    return BACKOFF_SECONDS[max(0, index)]
