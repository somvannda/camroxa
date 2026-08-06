"""Compact progress table presentation helpers."""

from __future__ import annotations

import re

from shared.lib.formatting import format_channel_role_label, percent_of
from shared.lib.video_runtime_inspection import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_NOT_STARTED,
    STATUS_PENDING,
)
from shared.models.platform import ProgressRow, ProgressRowMeta

_STAGE_LABELS = {
    "converter": "Export",
    "export": "Export",
    "merger": "Merge",
    "merge": "Merge",
}


def format_run_date_label(run_date: str) -> str:
    text = str(run_date or "").strip()
    if not text:
        return "—"
    if "→" in text:
        return text.split("→", 1)[0].strip()
    return text


def format_channel_label(channel: str, role: str) -> str:
    name = str(channel or "").strip() or "Unknown"
    role_key = format_channel_role_label(role)
    return f"{name} · {role_key}"


def format_album_label(album: str | None) -> str:
    text = str(album or "").strip()
    return text or "—"


def format_music_compact(row: ProgressRow) -> str:
    meta = row.meta
    base = str(row.music or "").strip() or f"{meta.saved}/{max(1, meta.expected)}"
    if meta.download_pending > 0:
        return f"{base} ↓"
    if meta.saved >= max(1, meta.expected):
        return f"{base} ✓"
    return base


def _image_badge(ready: int, total: int, status: str, label: str) -> str:
    normalized = str(status or "").strip().upper()
    count = f"{ready}/{max(1, total)}"
    if normalized == "READY" or (total > 0 and ready >= total):
        return f"{label} {count} ✓"
    if normalized == "SYNC":
        return f"{label} {count} ↓"
    if normalized == "FAILED":
        return f"{label} {count} ✗"
    if normalized in {"PENDING", "RUNNING", "PROCESSING"}:
        return f"{label} {count} …"
    return f"{label} {count}"


def format_images_compact(meta: ProgressRowMeta) -> str:
    bg = _image_badge(meta.bg_ready, meta.bg_total, meta.bg_status, "BG")
    th = _image_badge(meta.th_ready, meta.th_total, meta.th_status, "TH")
    return f"{bg} · {th}"


def format_pipeline_step_text(text: str) -> str:
    value = str(text or "").strip()
    if not value or value.lower().startswith("pending api parity"):
        return "—"
    return value


def format_export_compact(text: str) -> str:
    return _short_pipeline_label(text, kind="export")


def format_merge_compact(text: str) -> str:
    return _short_pipeline_label(text, kind="merge")


def _short_pipeline_label(text: str, *, kind: str) -> str:
    value = format_pipeline_step_text(text)
    if value == "—":
        return "—"
    lower = value.lower()
    if "waiting for image assets" in lower:
        return "Not started"
    if "no exports yet" in lower or ("pending" in lower and "no exports" in lower):
        return STATUS_PENDING
    if "exporting" in lower or "merging" in lower:
        return STATUS_IN_PROGRESS
    long_match = re.search(r"long\s+(\d+/\d+)", lower)
    reel_match = re.search(r"reel\s+(\d+/\d+)", lower)
    if kind == "export" and (long_match or reel_match):
        long_label = f"L {long_match.group(1)}" if long_match else "L —"
        reel_label = f"R {reel_match.group(1)}" if reel_match else "R —"
        if reel_match:
            return f"{long_label} · {reel_label}"
        return long_label
    if ("long completed" in lower or "long merged" in lower) and (
        "reel completed" in lower or "reel merged" in lower
    ):
        return STATUS_COMPLETED
    if "long completed" in lower or "long merged" in lower:
        return "Long completed"
    if "reel completed" in lower or "reel merged" in lower:
        return "Reel completed"
    if "long single" in lower or "reel single" in lower:
        return STATUS_COMPLETED
    if "long pending" in lower and "reel pending" in lower:
        return STATUS_PENDING
    if "waiting for branch" in lower or "pending · waiting" in lower:
        return STATUS_PENDING
    if "not required" in lower:
        return "N/A"
    if kind == "merge" and "failed" in lower:
        return "Failed"
    if len(value) > 24:
        return f"{value[:21]}…"
    return value


def resolve_progress_error_message(
    row: ProgressRow,
    *,
    effective_stage: str,
    effective_status: str,
    effective_notes: str,
) -> str | None:
    meta = row.meta
    messages: list[str] = []
    stage = str(effective_stage or "").strip().lower()
    status = str(effective_status or "").strip().lower()

    if stage == "error" or status == "failed":
        note = str(effective_notes or row.notes or "").strip()
        if note:
            messages.append(note)
    if meta.bg_status.upper() == "FAILED":
        messages.append("Background image generation failed.")
    if meta.th_status.upper() == "FAILED":
        messages.append("Thumbnail image generation failed.")
    if meta.youtube_failed > 0 or str(meta.youtube_status or "").upper() == "FAILED":
        messages.append("YouTube upload failed.")
    if str(meta.youtube_status or "").upper() == "BLOCKED":
        messages.append("YouTube upload is blocked until the channel is connected.")
    if meta.draft_failed_song_ids:
        count = len(meta.draft_failed_song_ids)
        messages.append(f"{count} draft generation failure{'s' if count != 1 else ''}.")
    if meta.suno_failed_song_ids:
        count = len(meta.suno_failed_song_ids)
        messages.append(f"{count} Suno submission failure{'s' if count != 1 else ''}.")

    cleaned = [message for message in messages if message]
    if not cleaned:
        return None
    return " ".join(dict.fromkeys(cleaned))


def format_stage_label(stage: str) -> str:
    key = str(stage or "").strip().lower()
    if not key:
        return "—"
    return _STAGE_LABELS.get(key, str(stage or "").strip())


def _normalize_progress_stage(stage: str) -> str:
    key = str(stage or "").strip().lower()
    if key in {"converter", "export"}:
        return "export"
    if key in {"merger", "merge"}:
        return "merge"
    return key


def _normalize_progress_status(status: str) -> str:
    key = str(status or "").strip().lower()
    if key in {"completed", "done", "success"}:
        return STATUS_COMPLETED.lower()
    if key in {"partial", "converting", "merging", "rendering", "downloading", "uploading", "running", "processing", "in progress"}:
        return STATUS_IN_PROGRESS.lower()
    if key in {"queued", "waiting", "preparing", "pending"}:
        return STATUS_PENDING.lower()
    if key in {"not started", "idle", "—", "-", ""}:
        return STATUS_NOT_STARTED.lower()
    return key


def compute_stage_progress_percent(
    row: ProgressRow,
    *,
    effective_stage: str,
    effective_status: str,
    converter_percent: int | None = None,
    merge_percent: int | None = None,
) -> str:
    stage = _normalize_progress_stage(effective_stage)
    status = _normalize_progress_status(effective_status)
    meta = row.meta

    if stage == "done" or status == "done":
        return "100%"
    if stage == "error" or status == "failed":
        return "—"

    if stage == "merge":
        if merge_percent is not None:
            return f"{merge_percent}%"
        if status == STATUS_COMPLETED.lower():
            return "100%"
        if status == STATUS_IN_PROGRESS.lower():
            return "50%"
        return "0%"

    if stage == "export":
        if converter_percent is not None:
            return f"{converter_percent}%"
        if status == STATUS_COMPLETED.lower():
            return "100%"
        if status == STATUS_IN_PROGRESS.lower():
            return "50%"
        return "0%"

    if stage == "youtube":
        if meta.youtube_success > 0:
            return "100%"
        if meta.youtube_pending > 0 or status in {"uploading", "queued"}:
            return "50%"
        return "0%"

    if stage == "image":
        parts: list[int] = []
        if meta.bg_total > 0:
            parts.append(percent_of(meta.bg_ready, meta.bg_total))
        if meta.th_total > 0:
            parts.append(percent_of(meta.th_ready, meta.th_total))
        if not parts:
            return "0%"
        return f"{round(sum(parts) / len(parts))}%"

    if stage == "music":
        # Disk-backed ``meta.saved`` (role MP3 count) after local overlay — never
        # inflate Progress % from API download flags or a pending midpoint.
        expected = max(1, meta.expected)
        return f"{percent_of(meta.saved, expected)}%"

    return "—"


def format_video_compact(converter: str, merge: str) -> str:
    converter_text = str(converter or "").strip()
    merge_text = str(merge or "").strip()
    if converter_text.lower().startswith("pending api parity"):
        converter_text = "—"
    if merge_text.lower().startswith("pending api parity"):
        merge_text = "—"
    if not converter_text and not merge_text:
        return "—"
    if not merge_text or merge_text == "—":
        return converter_text
    if not converter_text or converter_text == "—":
        return merge_text
    return f"{converter_text} · {merge_text}"


def format_youtube_compact(row: ProgressRow) -> str:
    text = str(row.youtube or "").strip()
    if not text or text == "—":
        meta = row.meta
        if meta.youtube_success > 0:
            return f"{STATUS_COMPLETED} ✓"
        if meta.youtube_failed > 0:
            return "Failed ✗"
        if meta.youtube_pending > 0:
            return f"{STATUS_IN_PROGRESS} …"
        if str(meta.youtube_status or "").upper() == "BLOCKED":
            return "Blocked"
        return "—"
    if text.lower() in {"ready", STATUS_COMPLETED.lower()}:
        return f"{STATUS_COMPLETED} ✓"
    if text.lower() == "failed":
        return "Failed ✗"
    if text.lower() in {"uploading", "queued"}:
        return f"{text} …"
    return text


def stage_status_rank(stage: str, status: str) -> str:
    stage_key = str(stage or "").strip().lower()
    status_key = str(status or "").strip().lower()
    if stage_key == "error" or status_key == "failed":
        return "failed"
    if stage_key == "done" or status_key == "done":
        return "success"
    if status_key in {"running", "rendering", "generating", "downloading", "converting", "merging", "uploading", "in progress"}:
        return "running"
    if status_key in {"queued", "waiting", "preparing", "pending"}:
        return "pending"
    if stage_key in {"converter", "export", "merger", "merge", "youtube"}:
        return "running"
    return "pending"
