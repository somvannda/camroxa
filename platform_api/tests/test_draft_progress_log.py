"""Draft / Suno progress log tests."""

from __future__ import annotations

import logging

from platform_api.services.draft_progress_log import (
    log_suno_callback_failed,
    log_suno_submit_failed,
    log_suno_submitted,
)


def test_suno_progress_log_emits_music_prefix(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="platform_api.music"):
        log_suno_submitted(
            batch_id="batch-abc-123",
            song_number=1,
            title="Test Song",
            task_id="task-uuid-1234",
        )
        log_suno_submit_failed(
            batch_id="batch-abc-123",
            song_number=1,
            title="Test Song",
            reason="External service unavailable",
        )
        log_suno_callback_failed(
            batch_id="batch-abc-123",
            song_number=1,
            title="Test Song",
            status="failed",
        )
    assert "[music] [batch batch-ab] [song #1] Suno submitted" in caplog.text
    assert "[music] [batch batch-ab] [song #1] Suno submit failed" in caplog.text
    assert "External service unavailable" in caplog.text
    assert "[music] [batch batch-ab] [song #1] Suno failed" in caplog.text
