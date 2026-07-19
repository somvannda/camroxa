"""Tests for music pipeline status labels."""

from __future__ import annotations

from shared.lib.music_status import format_song_pipeline_status, song_pipeline_status_tooltip


def test_format_song_pipeline_status_pending() -> None:
    assert format_song_pipeline_status("pending", None, None) == "Pending"
    assert format_song_pipeline_status("draft_ready", "PENDING", None) == "Pending"


def test_format_song_pipeline_status_success() -> None:
    assert format_song_pipeline_status("suno_success", "SUCCESS", None) == "Success"


def test_format_song_pipeline_status_failed_with_reason() -> None:
    message = (
        "Suno flagged sensitive content in the lyrics or style. "
        "Edit the prompt and try again. Explicit word: violence"
    )
    label = format_song_pipeline_status("suno_failed", "SENSITIVE_WORD_ERROR", message)
    assert label.startswith("Failed (Reason:")
    assert "Explicit word: violence" in label
    assert len(label) <= 120 + len("Failed (Reason: )")


def test_format_song_pipeline_status_failed_without_reason() -> None:
    assert format_song_pipeline_status("suno_failed", "REJECTED", None) == "Failed"


def test_song_pipeline_status_tooltip_returns_full_reason() -> None:
    message = "Suno rejected this song (content policy). Review the lyrics and style prompt, then try again."
    tooltip = song_pipeline_status_tooltip("suno_failed", "REJECTED", message)
    assert tooltip == message


def test_song_pipeline_status_tooltip_none_for_success() -> None:
    assert song_pipeline_status_tooltip("suno_success", "SUCCESS", "ignored") is None


def test_is_song_suno_retry_eligible_draft_ready() -> None:
    from shared.lib.music_status import is_song_suno_retry_eligible

    assert is_song_suno_retry_eligible("draft_ready", None) is True


def test_is_song_suno_retry_eligible_stuck_suno_pending() -> None:
    from shared.lib.music_status import is_song_suno_retry_eligible

    assert is_song_suno_retry_eligible("suno_pending", "failed") is True
    assert is_song_suno_retry_eligible("suno_pending", "FAILED") is True


def test_is_song_suno_retry_eligible_not_draft_failed() -> None:
    from shared.lib.music_status import is_song_suno_retry_eligible

    assert is_song_suno_retry_eligible("draft_failed", None) is False
