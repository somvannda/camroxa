"""Canonical job_queue.job_type values drained by platform_api.worker."""

from __future__ import annotations

import os

JOB_EXECUTE_BATCH = "execute_batch"
JOB_DRAFT = "draft"
JOB_SUNO_SUBMIT = "suno_submit"
JOB_WEB_MUSIC_GENERATE = "web_music_generate"
JOB_RETRY_SONG_DRAFT = "retry_song_draft"
JOB_RETRY_SONG_SUNO = "retry_song_suno"
JOB_RUN_IMAGE_JOBS = "run_image_jobs"
JOB_RUN_YOUTUBE_UPLOADS = "run_youtube_uploads"

WORKER_JOB_TYPES = frozenset(
    {
        JOB_EXECUTE_BATCH,
        JOB_DRAFT,
        JOB_SUNO_SUBMIT,
        JOB_WEB_MUSIC_GENERATE,
        JOB_RETRY_SONG_DRAFT,
        JOB_RETRY_SONG_SUNO,
        JOB_RUN_IMAGE_JOBS,
        JOB_RUN_YOUTUBE_UPLOADS,
    }
)

# Higher priority is claimed first (ORDER BY priority DESC).
# execute_batch must outrank draft/suno so new batches fan out under load.
PRI_EXECUTE_BATCH = 25
PRI_RETRY = 20
PRI_SUNO_SUBMIT = 18
PRI_WEB_MUSIC_PAID = 16
PRI_WEB_MUSIC_FREE = 8
PRI_RUN_IMAGE_JOBS = 12
PRI_YOUTUBE_UPLOADS = 6

# Packs-only billing: credits are the only gate on Web Create, so an unsubscribed
# (pack/Free-plan) user can already queue a 5/10/20-song batch. The per-user cap
# is queue protection only, which is why both tiers share one number.
WEB_MUSIC_GENERATE_QUEUE_CAP_PAID = 20
WEB_MUSIC_GENERATE_QUEUE_CAP_FREE = 20


def draft_priority_for_index(batch_index: int) -> int:
    """Earlier songs in a batch get higher draft priority (20 → 5)."""
    return max(5, 20 - min(int(batch_index), 15))


# Stage shards for systemd multi-worker deploy (CAMXORA_WORKER_JOB_TYPES).
STAGE_DRAFT_TYPES = frozenset({JOB_EXECUTE_BATCH, JOB_DRAFT, JOB_RETRY_SONG_DRAFT})
STAGE_SUNO_TYPES = frozenset({JOB_SUNO_SUBMIT, JOB_RETRY_SONG_SUNO, JOB_WEB_MUSIC_GENERATE})
STAGE_IMAGES_TYPES = frozenset({JOB_RUN_IMAGE_JOBS, JOB_RUN_YOUTUBE_UPLOADS})

STAGE_PRESETS: dict[str, frozenset[str]] = {
    "draft": STAGE_DRAFT_TYPES,
    "suno": STAGE_SUNO_TYPES,
    "images": STAGE_IMAGES_TYPES,
    "all": WORKER_JOB_TYPES,
}


def stage_for_job_type(job_type: str) -> str:
    """Map a job_queue.job_type to the worker stage shard label."""
    jt = (job_type or "").strip()
    if jt in STAGE_DRAFT_TYPES:
        return "draft"
    if jt in STAGE_SUNO_TYPES:
        return "suno"
    if jt in STAGE_IMAGES_TYPES:
        return "images"
    return "other"


def resolve_worker_job_types(raw: str | None = None) -> frozenset[str]:
    """Parse CAMXORA_WORKER_JOB_TYPES (comma list or preset: draft|suno|images|all)."""
    value = (raw if raw is not None else os.environ.get("CAMXORA_WORKER_JOB_TYPES", "")).strip()
    if not value:
        return WORKER_JOB_TYPES
    lowered = value.lower()
    if lowered in STAGE_PRESETS:
        return STAGE_PRESETS[lowered]
    parsed = {part.strip() for part in value.split(",") if part.strip()}
    unknown = parsed - WORKER_JOB_TYPES
    if unknown:
        raise ValueError(f"Unknown CAMXORA_WORKER_JOB_TYPES: {sorted(unknown)}")
    if not parsed:
        return WORKER_JOB_TYPES
    return frozenset(parsed)
