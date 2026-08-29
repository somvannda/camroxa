"""Image workspace helpers — port of ImageWorkspacePage.tsx logic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from shared.models.auth import ProfileResponse
from shared.models.platform import ImageJobListItem, MusicHistoryBatch

# Match platform_api.services.generation_service.IMAGE_MAX_PROMPT_LENGTH
IMAGE_PROMPT_MAX_CHARS = 5000


@dataclass(frozen=True, slots=True)
class ImageUiSettings:
    image_background_prompt: str
    image_thumbnail_prompt: str


def clamp_image_prompt(text: str | None, *, max_chars: int = IMAGE_PROMPT_MAX_CHARS) -> str:
    """Return prompt text truncated to the hard UI/API allowance."""
    value = text if isinstance(text, str) else ""
    limit = max(1, int(max_chars))
    if len(value) <= limit:
        return value
    return value[:limit]


@dataclass(frozen=True, slots=True)
class QueueRow:
    key: str
    batch_id: str
    song_id: str
    album_label: str
    track_count: int
    date_label: str
    profile_name: str
    role: str
    bg_job: ImageJobListItem | None
    th_job: ImageJobListItem | None
    bg_jobs: tuple[ImageJobListItem, ...] = ()
    th_jobs: tuple[ImageJobListItem, ...] = ()


_STATUS_RANK = {
    "success": 4,
    "running": 3,
    "pending": 2,
    "failed": 1,
    "cancelled": 0,
}


def _job_status_rank(status: str | None) -> int:
    return _STATUS_RANK.get(str(status or "").strip().lower(), -1)


def _job_sort_key(job: ImageJobListItem) -> tuple[int, str]:
    return (_job_status_rank(job.status), str(job.updated_at or job.created_at or ""))


def pick_preferred_image_job(
    current: ImageJobListItem | None,
    candidate: ImageJobListItem,
) -> ImageJobListItem:
    if current is None:
        return candidate
    return candidate if _job_sort_key(candidate) >= _job_sort_key(current) else current


def _build_batch_album_labels(batches: list[MusicHistoryBatch]) -> dict[tuple[str, str], str]:
    labels: dict[tuple[str, str], str] = {}
    for batch in batches:
        fallback = ""
        for song in batch.songs:
            candidate = str(song.album or "").strip()
            if candidate:
                fallback = candidate
                break
        if not fallback:
            for song in batch.songs:
                candidate = str(song.title or "").strip()
                if candidate:
                    fallback = candidate
                    break
        status = str(batch.status or "").strip().lower()
        if status == "manual_image":
            fallback = "Not available"
        else:
            fallback = fallback or "Untitled album"
        ok_album = str(batch.ok_album or "").strip() or fallback
        if ok_album.lower() == "not available":
            ok_album = "Not available"
        alt_album = str(batch.alt_album or "").strip()
        if not alt_album or alt_album.lower() == ok_album.lower():
            alt_album = f"{ok_album} II" if ok_album else f"{fallback} II"
        labels[(batch.batch_id, "ok")] = ok_album
        labels[(batch.batch_id, "alt")] = alt_album or "—"
    return labels


def normalize_image_prompt_settings(settings: dict[str, object] | None) -> ImageUiSettings:
    raw = settings or {}
    legacy_prompt = raw.get("imagePrompt")
    legacy = legacy_prompt if isinstance(legacy_prompt, str) else ""
    background = raw.get("imageBackgroundPrompt")
    thumbnail = raw.get("imageThumbnailPrompt")
    return ImageUiSettings(
        image_background_prompt=clamp_image_prompt(
            background if isinstance(background, str) else legacy
        ),
        image_thumbnail_prompt=clamp_image_prompt(
            thumbnail if isinstance(thumbnail, str) else ""
        ),
    )


def batch_date_label(batch: MusicHistoryBatch) -> str:
    from_date = batch.from_date or batch.created_at[:10]
    to_date = batch.to_date or batch.updated_at[:10]
    return from_date if from_date == to_date else f"{from_date} → {to_date}"


def batch_is_within_range(batch: MusicHistoryBatch, from_date: str, to_date: str) -> bool:
    batch_from = batch.from_date or batch.created_at[:10]
    batch_to = batch.to_date or batch.updated_at[:10]
    if from_date and batch_to < from_date:
        return False
    if to_date and batch_from > to_date:
        return False
    return True


def format_job_status(status: str | None) -> str:
    normalized = str(status or "").strip().lower()
    return normalized or "—"


def format_queue_role_status(jobs: tuple[ImageJobListItem, ...] | list[ImageJobListItem]) -> str:
    if not jobs:
        return "—"
    total = len(jobs)
    success = sum(1 for job in jobs if str(job.status or "").strip().lower() == "success")
    running = sum(1 for job in jobs if str(job.status or "").strip().lower() == "running")
    failed = sum(1 for job in jobs if str(job.status or "").strip().lower() == "failed")
    pending = sum(1 for job in jobs if str(job.status or "").strip().lower() == "pending")
    if success == total:
        return "✓"
    if failed:
        return f"{failed} fail"
    if running:
        return f"{running} run"
    if pending == total:
        return f"{pending} wait"
    return f"{success}/{total}"


def basename_or_dash(path: str | None) -> str:
    if not path:
        return "—"
    return Path(path).name or "—"


def build_queue_rows(
    jobs: list[ImageJobListItem],
    batches: list[MusicHistoryBatch],
    profiles: list[ProfileResponse],
) -> list[QueueRow]:
    profile_by_id = {profile.id: profile for profile in profiles}
    batch_by_id = {batch.batch_id: batch for batch in batches}
    batch_meta = {batch.batch_id: batch_date_label(batch) for batch in batches}
    album_labels = _build_batch_album_labels(batches)
    track_counts = {batch.batch_id: len(batch.songs) for batch in batches}
    rows: dict[str, QueueRow] = {}

    for job in jobs:
        batch_id = job.batch_id or ""
        profile_id = job.profile_id or ""
        role = job.channel_role or ""
        key = f"{batch_id}-{profile_id}-{role}"
        batch = batch_by_id.get(batch_id)
        is_manual_image = str(getattr(batch, "status", "") or "").strip().lower() == "manual_image"
        if is_manual_image:
            profile_name = "Not available"
            display_role = "n/a"
        else:
            profile_name = (
                profile_by_id.get(profile_id).name if profile_id in profile_by_id else profile_id or "Unknown"
            )
            display_role = role
        existing = rows.get(key)
        if existing is None:
            existing = QueueRow(
                key=key,
                batch_id=batch_id,
                song_id=job.song_id or "",
                album_label=album_labels.get((batch_id, role.lower()), "Untitled album"),
                track_count=track_counts.get(batch_id, 0),
                date_label=batch_meta.get(batch_id, "Unknown date"),
                profile_name=profile_name,
                role=display_role,
                bg_job=None,
                th_job=None,
                bg_jobs=(),
                th_jobs=(),
            )
        bg_jobs = list(existing.bg_jobs)
        th_jobs = list(existing.th_jobs)
        bg_job = existing.bg_job
        th_job = existing.th_job
        if job.kind == "background":
            bg_jobs.append(job)
            bg_job = pick_preferred_image_job(bg_job, job)
        elif job.kind == "thumbnail":
            th_jobs.append(job)
            th_job = pick_preferred_image_job(th_job, job)
        if not existing.song_id and job.song_id:
            song_id = job.song_id
        else:
            song_id = existing.song_id
        existing = QueueRow(
            key=existing.key,
            batch_id=existing.batch_id,
            song_id=song_id,
            album_label=existing.album_label,
            track_count=existing.track_count,
            date_label=existing.date_label,
            profile_name=existing.profile_name,
            role=existing.role,
            bg_job=bg_job,
            th_job=th_job,
            bg_jobs=tuple(bg_jobs),
            th_jobs=tuple(th_jobs),
        )
        rows[key] = existing

    return sorted(
        rows.values(),
        key=lambda row: (row.date_label, row.album_label, row.role, row.profile_name),
    )


def build_queue_status_summary(
    *,
    grouped_row_count: int,
    filtered_batch_count: int,
    rows: list[QueueRow],
) -> str:
    if not grouped_row_count:
        if filtered_batch_count:
            return "No image jobs yet for this date range."
        return "No batches found in the selected date range."

    visible_jobs: list[ImageJobListItem] = []
    for row in rows:
        visible_jobs.extend(row.bg_jobs)
        visible_jobs.extend(row.th_jobs)

    pending = sum(1 for job in visible_jobs if job.status == "pending")
    running = sum(1 for job in visible_jobs if job.status == "running")
    failed = sum(1 for job in visible_jobs if job.status == "failed")
    success = sum(1 for job in visible_jobs if job.status == "success")
    return f"Rows {grouped_row_count} · Pending {pending} · Running {running} · Failed {failed} · Ready {success}"


_QUEUE_STATUS_SUMMARY_RE = re.compile(
    r"^Rows (\d+) · Pending (\d+) · Running (\d+) · Failed (\d+) · Ready (\d+)$"
)


def parse_queue_status_counts(summary: str) -> dict[str, int] | None:
    match = _QUEUE_STATUS_SUMMARY_RE.match(str(summary or "").strip())
    if match is None:
        return None
    rows, pending, running, failed, ready = (int(part) for part in match.groups())
    return {
        "rows": rows,
        "pending": pending,
        "running": running,
        "failed": failed,
        "ready": ready,
    }


def build_footer_detail(row: QueueRow | None) -> str:
    if row is None:
        return ""
    parts: list[str] = []
    if row.track_count > 1:
        parts.append(f"{row.track_count} tracks in batch")
    bg_errors = sorted({str(job.error or "").strip() for job in row.bg_jobs if job.error})
    th_errors = sorted({str(job.error or "").strip() for job in row.th_jobs if job.error})
    if bg_errors:
        parts.append(f"BG error: {bg_errors[0]}")
    if th_errors:
        parts.append(f"TH error: {th_errors[0]}")
    if row.bg_job and row.bg_job.input_image_path:
        parts.append(f"BG sample: {basename_or_dash(row.bg_job.input_image_path)}")
    if row.th_job and row.th_job.style_reference_path:
        parts.append(f"TH style: {basename_or_dash(row.th_job.style_reference_path)}")
    return " · ".join(parts)


def split_queue_footer_detail(detail: str) -> tuple[str, str]:
    """Split queue footer copy into non-error info and BG/TH error text."""
    info: list[str] = []
    errors: list[str] = []
    for part in str(detail or "").split(" · "):
        text = part.strip()
        if not text or "tracks in batch" in text.lower():
            continue
        lowered = text.lower()
        if lowered.startswith("bg error:") or lowered.startswith("th error:"):
            errors.append(text)
        else:
            info.append(text)
    return " · ".join(info), " · ".join(errors)


def filter_batches_by_date(
    batches: list[MusicHistoryBatch],
    from_date: str,
    to_date: str,
) -> list[MusicHistoryBatch]:
    return [batch for batch in batches if batch_is_within_range(batch, from_date, to_date)]


def filter_jobs_by_batches(
    jobs: list[ImageJobListItem],
    batch_ids: set[str],
) -> list[ImageJobListItem]:
    if not batch_ids:
        return []
    return [job for job in jobs if job.batch_id and job.batch_id in batch_ids]
