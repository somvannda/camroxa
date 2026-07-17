"""Display helpers for music history rows."""

from __future__ import annotations

_GENERATING_STATUSES = frozenset({"pending", "processing", "drafting"})


def is_song_title_generating(status: str | None, title: str | None) -> bool:
    """True when a song row should show the animated Generating... label."""
    if str(title or "").strip():
        return False
    normalized = str(status or "pending").strip().lower()
    return normalized in _GENERATING_STATUSES
