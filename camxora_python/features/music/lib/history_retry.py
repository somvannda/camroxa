"""Music history retry helpers."""

from __future__ import annotations

from shared.models.platform import MusicHistoryListResponse


def history_track_number(history: MusicHistoryListResponse, song_id: str) -> int | None:
    """Return 1-based batch track number for a song id, if present in loaded history."""
    target = str(song_id or "").strip()
    if not target:
        return None
    for batch in history.batches:
        for song in batch.songs:
            if song.song_id == target:
                return int(song.batch_index) + 1
    return None
