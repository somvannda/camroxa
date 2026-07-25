"""Tests for Music History pipeline recovery target collection."""

from __future__ import annotations

from features.music.lib.pipeline_recovery import (
    assess_lyrics_health,
    classify_suno_recovery_kind,
    collect_recovery_targets,
)
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


def test_assess_lyrics_health_detects_corrupt_and_oversized() -> None:
    assert assess_lyrics_health("") == "empty"
    assert assess_lyrics_health("[Verse]\nHello night") == "healthy"
    assert assess_lyrics_health("[Verse]\n" + ("line\n" * 3000)) == "oversized"
    garbage = "[Intro]\nok\n" + ("漢字العربية한국어" * 80) + "\nSpringApplication JSONObject"
    assert assess_lyrics_health(garbage) == "corrupt"


def test_corrupt_lyrics_are_skipped_not_suno_retried() -> None:
    garbage = "[Intro]\nWe coastal saint\n" + ("漢字العربية" * 100) + "\ngithubusercontent"
    song = MusicHistorySong(
        song_id="bad",
        batch_index=0,
        status="suno_failed",
        suno_status="FAILED",
        suno_error_message="",
        lyrics=garbage,
    )
    kind, reason = classify_suno_recovery_kind(song)
    assert kind == "skip"
    assert reason == "corrupt_lyrics"

    batch = MusicHistoryBatch(
        batch_id="b",
        ok_profile_id="p",
        songs=[song],
    )
    targets = collect_recovery_targets([batch])
    assert len(targets) == 1
    assert targets[0].kind == "skip"


def test_oversized_healthy_ascii_lyrics_rewrite() -> None:
    lyrics = "[Verse]\n" + ("A calm line about the evening road.\n" * 200)
    song = MusicHistorySong(
        song_id="big",
        batch_index=0,
        status="suno_failed",
        lyrics=lyrics,
    )
    kind, reason = classify_suno_recovery_kind(song)
    assert kind == "suno_rewrite"
    assert reason == "oversized_lyrics"


def test_collect_batch_rewrite_targets_forces_rewrite_and_skips_corrupt() -> None:
    from features.music.lib.pipeline_recovery import collect_batch_rewrite_targets

    garbage = "[Intro]\nok\n" + ("漢字العربية한국어" * 80)
    batch = MusicHistoryBatch(
        batch_id="batch-rw",
        ok_profile_id="profile-ok",
        songs=[
            MusicHistorySong(
                song_id="good",
                batch_index=0,
                status="suno_failed",
                suno_status="FAILED",
                suno_error_message="timeout",
                lyrics="[Verse]\nHello world\nKeep it short",
                title="Ok",
            ),
            MusicHistorySong(
                song_id="bad",
                batch_index=1,
                status="suno_failed",
                lyrics=garbage,
            ),
            MusicHistorySong(
                song_id="draft",
                batch_index=2,
                status="draft_failed",
            ),
        ],
    )
    targets = collect_batch_rewrite_targets(batch)
    assert [t.song_id for t in targets] == ["good"]
    assert targets[0].kind == "suno_rewrite"
    assert targets[0].reason.startswith("batch_rewrite:")
