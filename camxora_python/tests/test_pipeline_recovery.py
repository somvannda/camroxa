"""Tests for Music History pipeline recovery target collection."""

from __future__ import annotations

from features.music.lib.pipeline_recovery import collect_recovery_targets
from shared.models.platform import MusicHistoryBatch, MusicHistorySong


def test_collect_recovery_targets_classifies_draft_suno_and_rewrite() -> None:
    batch = MusicHistoryBatch(
        batch_id="batch-1",
        ok_profile_id="profile-ok",
        songs=[
            MusicHistorySong(song_id="d1", batch_index=0, status="draft_failed"),
            MusicHistorySong(
                song_id="s1",
                batch_index=1,
                status="suno_failed",
                suno_status="REJECTED",
                suno_error_message="content policy",
                lyrics="[Verse]\nHello world",
                title="Song",
            ),
            MusicHistorySong(
                song_id="s2",
                batch_index=2,
                status="suno_failed",
                suno_status="FAILED",
                suno_error_message="timeout",
                lyrics="[Verse]\nOk",
            ),
            MusicHistorySong(
                song_id="ok",
                batch_index=3,
                status="suno_success",
                suno_status="SUCCESS",
            ),
        ],
    )
    targets = collect_recovery_targets([batch])
    by_id = {t.song_id: t.kind for t in targets}
    assert by_id["d1"] == "draft"
    assert by_id["s1"] == "suno_rewrite"
    assert by_id["s2"] == "suno_retry"
    assert "ok" not in by_id
