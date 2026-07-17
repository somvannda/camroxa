"""Music history label helpers."""

from __future__ import annotations

from shared.lib.music_history_labels import is_song_title_generating


def test_pending_without_title_is_generating() -> None:
    assert is_song_title_generating("pending", None) is True
    assert is_song_title_generating("pending", "") is True


def test_title_present_is_not_generating() -> None:
    assert is_song_title_generating("pending", "Midnight Run") is False


def test_draft_failed_without_title_is_not_generating() -> None:
    assert is_song_title_generating("draft_failed", None) is False
