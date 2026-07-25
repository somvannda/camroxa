"""Tests for background pipeline recovery coordinator eligibility."""

from __future__ import annotations

from features.music.lib.pipeline_recovery import RecoveryTarget
from shared.services.pipeline_recovery_coordinator import PipelineRecoveryCoordinator


def test_filter_targets_respects_cooldown_and_session_cap(qapp) -> None:
    api = object()
    coordinator = PipelineRecoveryCoordinator(api)  # type: ignore[arg-type]
    targets = [
        RecoveryTarget(batch_id="b1", song_id="s1", kind="draft"),
        RecoveryTarget(batch_id="b1", song_id="s2", kind="suno_retry", lyrics_hash="aaa"),
        RecoveryTarget(batch_id="b1", song_id="s3", kind="suno_rewrite", lyrics_hash="bbb"),
        RecoveryTarget(batch_id="b1", song_id="s4", kind="draft"),
    ]
    first = coordinator._filter_targets(targets)
    assert [t.song_id for t in first] == ["s1", "s2", "s3"]

    coordinator._mark_attempted(tuple(first))
    second = coordinator._filter_targets(targets)
    # s1-s3 on cooldown; s4 still eligible
    assert [t.song_id for t in second] == ["s4"]

    coordinator._mark_attempted(tuple(second))
    coordinator._song_state["s4"].attempts = 2
    third = coordinator._filter_targets(targets)
    assert third == []


def test_filter_skips_busy_songs_and_escalates_same_hash_retry(qapp) -> None:
    api = object()
    coordinator = PipelineRecoveryCoordinator(api)  # type: ignore[arg-type]
    retry = RecoveryTarget(
        batch_id="b1",
        song_id="s2",
        kind="suno_retry",
        lyrics_hash="same",
        lyrics="[Verse]\nOk",
    )
    coordinator._mark_attempted([retry])
    # Clear cooldown/busy so escalation path is exercised.
    coordinator._busy_until.clear()
    coordinator._song_state["s2"].last_attempt_at = 0.0

    escalated = coordinator._filter_targets([retry])
    assert len(escalated) == 1
    assert escalated[0].kind == "suno_rewrite"
    assert escalated[0].reason == "escalate_after_same_hash_retry"

    coordinator.mark_song_busy("s2", seconds=300)
    assert coordinator._filter_targets([retry]) == []
