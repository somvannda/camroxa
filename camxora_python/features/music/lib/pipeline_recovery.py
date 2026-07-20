"""Pipeline failure recovery helpers for Music History."""

from __future__ import annotations

from dataclasses import dataclass

from shared.lib.music_status import classify_song_pipeline_bucket, is_song_suno_batch_retry_target
from shared.models.platform import MusicHistoryBatch, MusicHistorySong


@dataclass(frozen=True, slots=True)
class RecoveryTarget:
    batch_id: str
    song_id: str
    kind: str  # draft | suno_retry | suno_rewrite
    channel_profile_id: str | None = None
    title: str | None = None
    album: str | None = None
    lyrics: str | None = None
    description: str | None = None
    structure: str | None = None


def _looks_like_content_policy_failure(song: MusicHistorySong) -> bool:
    status = str(song.suno_status or song.status or "").strip().upper()
    if status in {
        "REJECTED",
        "SENSITIVE_WORD_ERROR",
        "SENSITIVE_CONTENT",
        "CONTENT_POLICY",
        "POLICY_VIOLATION",
    }:
        return True
    text = str(song.suno_error_message or "").strip().lower()
    return any(
        token in text
        for token in (
            "content policy",
            "policy violation",
            "sensitive",
            "rejected",
            "producer tag",
            "moderat",
        )
    )


def collect_recovery_targets(batches: list[MusicHistoryBatch]) -> list[RecoveryTarget]:
    """Scan history batches for failed songs that can be auto-recovered."""
    targets: list[RecoveryTarget] = []
    for batch in batches:
        ok_profile = str(batch.ok_profile_id or "").strip() or None
        for song in batch.songs:
            song_status = str(song.status or "").strip().lower()
            if song_status == "draft_failed":
                targets.append(
                    RecoveryTarget(
                        batch_id=batch.batch_id,
                        song_id=song.song_id,
                        kind="draft",
                    )
                )
                continue
            if not is_song_suno_batch_retry_target(song.status, song.suno_status):
                # Still allow content-policy rewrite when classify says failed.
                if classify_song_pipeline_bucket(song.status, song.suno_status) != "failed":
                    continue
            lyrics = str(song.lyrics or "").strip()
            if _looks_like_content_policy_failure(song) and lyrics:
                targets.append(
                    RecoveryTarget(
                        batch_id=batch.batch_id,
                        song_id=song.song_id,
                        kind="suno_rewrite",
                        channel_profile_id=ok_profile,
                        title=song.title,
                        album=song.album,
                        lyrics=lyrics,
                        description=song.description_name,
                        structure=song.structure_name,
                    )
                )
            elif is_song_suno_batch_retry_target(song.status, song.suno_status):
                targets.append(
                    RecoveryTarget(
                        batch_id=batch.batch_id,
                        song_id=song.song_id,
                        kind="suno_retry",
                    )
                )
    return targets
