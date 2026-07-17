"""Compact progress table presentation helpers."""

from __future__ import annotations

import re

from shared.lib.formatting import format_channel_role_label, percent_of
from shared.models.platform import ProgressRow, ProgressRowMeta


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
        return "Needs images"
    if "assets ready" in lower and "no exports" in lower:
        return "Ready"
    if "converting" in lower or "merging" in lower:
        return value.split(".", 1)[0][:24]
    long_match = re.search(r"long\s+(\d+/\d+)", lower)
    reel_match = re.search(r"reel\s+(\d+/\d+)", lower)
    if kind == "export" and (long_match or reel_match):
        long_label = f"L {long_match.group(1)}" if long_match else "L —"
        reel_label = f"R {reel_match.group(1)}" if reel_match else "R —"
        return f"{long_label} · {reel_label}"
    if "long merged" in lower and "reel merged" in lower:
        return "Done"
    if "long merged" in lower:
        return "Long ✓"
    if "reel merged" in lower:
        return "Reel ✓"
    if "long single" in lower or "reel single" in lower:
        return "Single"
    if "long pending" in lower and "reel pending" in lower:
        return "Pending"
    if "ready for merge" in lower:
        return "Ready"
    if "not required" in lower:
        return "N/A"
    if "waiting for branch" in lower:
        return "Waiting"
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
    return str(stage or "").strip() or "—"


def compute_stage_progress_percent(
    row: ProgressRow,
    *,
    effective_stage: str,
    effective_status: str,
    converter_percent: int | None = None,
    merge_percent: int | None = None,
) -> str:
    stage = str(effective_stage or "").strip().lower()
    status = str(effective_status or "").strip().lower()
    meta = row.meta

    if stage == "done" or status == "done":
        return "100%"
    if stage == "error" or status == "failed":
        return "—"

    if stage == "merger":
        if merge_percent is not None:
            return f"{merge_percent}%"
        if status == "completed":
            return "100%"
        if status == "merging":
            return "50%"
        return "0%"

    if stage == "converter":
        if converter_percent is not None:
            return f"{converter_percent}%"
        if status == "completed":
            return "100%"
        if status in {"converting", "rendering"}:
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
        expected = max(1, meta.expected)
        if meta.download_pending > 0 and meta.download_ready > meta.saved:
            midpoint = meta.saved + max(1, meta.download_pending) // 2
            return f"{percent_of(midpoint, expected)}%"
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
            return "Ready ✓"
        if meta.youtube_failed > 0:
            return "Failed ✗"
        if meta.youtube_pending > 0:
            return "Uploading …"
        if str(meta.youtube_status or "").upper() == "BLOCKED":
            return "Blocked"
        return "—"
    if text.lower() == "ready":
        return "Ready ✓"
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
    if status_key in {"running", "rendering", "generating", "downloading", "converting", "merging", "uploading"}:
        return "running"
    if status_key in {"queued", "waiting", "preparing"}:
        return "pending"
    if stage_key in {"converter", "merger", "youtube"}:
        return "running"
    return "pending"
