"""Pipeline failure recovery helpers for Music History."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from shared.lib.music_status import classify_song_pipeline_bucket, is_song_suno_batch_retry_target
from shared.models.platform import MusicHistoryBatch, MusicHistorySong

# Suno payloads much larger than this usually fail or are rewrite-poisoned.
_MAX_HEALTHY_LYRICS_LEN = 4500
# Mixed-script dumps from broken rewrite/sanitize tails.
_SCRIPT_RE = re.compile(
    r"[\u0400-\u04ff\u0600-\u06ff\u0900-\u097f\u0e00-\u0e7f"
    r"\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]"
)
_GARBAGE_TOKEN_RE = re.compile(
    r"(springapplication|jsonobject|githubusercontent|getmethod|"
    r"formattingenabled|toolstripbutton|ecore\b|remove\.spring|"
    r"sanitize value forbidden|\.vertices\b)",
    re.IGNORECASE,
)

LyricHealth = Literal["empty", "healthy", "oversized", "corrupt"]


@dataclass(frozen=True, slots=True)
class RecoveryTarget:
    batch_id: str
    song_id: str
    kind: str  # draft | suno_retry | suno_rewrite | skip
    channel_profile_id: str | None = None
    title: str | None = None
    album: str | None = None
    lyrics: str | None = None
    mood_id: str | None = None
    structure_id: str | None = None
    reason: str = ""
    lyrics_hash: str = ""


def lyrics_hash(lyrics: str | None) -> str:
    text = str(lyrics or "").strip()
    if not text:
        return ""
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def assess_lyrics_health(lyrics: str | None) -> LyricHealth:
    """Classify lyric payload health for recovery decisions."""
    text = str(lyrics or "").strip()
    if not text:
        return "empty"
    if _GARBAGE_TOKEN_RE.search(text):
        return "corrupt"
    script_hits = len(_SCRIPT_RE.findall(text))
    if script_hits >= 40 or (len(text) >= 800 and script_hits / max(len(text), 1) >= 0.04):
        return "corrupt"
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    if len(text) >= 1200 and non_ascii / max(len(text), 1) >= 0.12:
        return "corrupt"
    if len(text) > _MAX_HEALTHY_LYRICS_LEN:
        return "oversized"
    return "healthy"


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
            "blocked",
            "blocklist",
        )
    )


def _looks_like_transient_suno_failure(song: MusicHistorySong) -> bool:
    text = str(song.suno_error_message or "").strip().lower()
    status = str(song.suno_status or "").strip().upper()
    if status in {"TIMEOUT", "NETWORK_ERROR", "RATE_LIMITED", "TEMPORARY_ERROR"}:
        return True
    return any(
        token in text
        for token in (
            "timeout",
            "timed out",
            "temporarily",
            "try again",
            "rate limit",
            "429",
            "502",
            "503",
            "504",
            "network",
            "connection",
            "unavailable",
        )
    )


def classify_suno_recovery_kind(song: MusicHistorySong) -> tuple[str, str]:
    """Return (kind, reason) for a failed/stuck Suno song."""
    lyrics = str(song.lyrics or "").strip()
    health = assess_lyrics_health(lyrics)

    if health == "empty":
        return "skip", "empty_lyrics"
    if health == "corrupt":
        # Rewriting poison text usually makes it worse; needs a fresh draft.
        return "skip", "corrupt_lyrics"
    if health == "oversized":
        return "suno_rewrite", "oversized_lyrics"
    if _looks_like_content_policy_failure(song):
        return "suno_rewrite", "content_policy"
    if _looks_like_transient_suno_failure(song):
        return "suno_retry", "transient_error"
    # Generic suno_failed with healthy lyrics: retry once-style path.
    if is_song_suno_batch_retry_target(song.status, song.suno_status):
        return "suno_retry", "suno_failed"
    if classify_song_pipeline_bucket(song.status, song.suno_status) == "failed":
        return "suno_rewrite", "failed_without_provider_status"
    return "skip", "not_eligible"


def collect_batch_rewrite_targets(batch: MusicHistoryBatch) -> list[RecoveryTarget]:
    """Failed songs in one batch that can be rewrite→Suno (skips corrupt / empty / drafts)."""
    ok_profile = str(batch.ok_profile_id or "").strip() or None
    targets: list[RecoveryTarget] = []
    for song in batch.songs:
        song_status = str(song.status or "").strip().lower()
        if song_status == "draft_failed":
            continue
        bucket = classify_song_pipeline_bucket(song.status, song.suno_status)
        if not is_song_suno_batch_retry_target(song.status, song.suno_status):
            if bucket != "failed":
                continue
        kind, reason = classify_suno_recovery_kind(song)
        if kind in {"skip", "draft"}:
            continue
        lyrics = str(song.lyrics or "").strip()
        if not lyrics:
            continue
        # Batch rewrite always polish→Suno (not blind Suno retry).
        targets.append(
            RecoveryTarget(
                batch_id=batch.batch_id,
                song_id=song.song_id,
                kind="suno_rewrite",
                channel_profile_id=ok_profile,
                title=song.title,
                album=song.album,
                lyrics=lyrics,
                mood_id=song.mood_id,
                structure_id=song.structure_id,
                reason=f"batch_rewrite:{reason}",
                lyrics_hash=lyrics_hash(lyrics),
            )
        )
    return targets


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
                        reason="draft_failed",
                    )
                )
                continue

            bucket = classify_song_pipeline_bucket(song.status, song.suno_status)
            if not is_song_suno_batch_retry_target(song.status, song.suno_status):
                if bucket != "failed":
                    continue

            kind, reason = classify_suno_recovery_kind(song)
            lyrics = str(song.lyrics or "").strip() or None
            targets.append(
                RecoveryTarget(
                    batch_id=batch.batch_id,
                    song_id=song.song_id,
                    kind=kind,
                    channel_profile_id=ok_profile,
                    title=song.title,
                    album=song.album,
                    lyrics=lyrics,
                    mood_id=song.mood_id,
                    structure_id=song.structure_id,
                    reason=reason,
                    lyrics_hash=lyrics_hash(lyrics),
                )
            )
    return targets
