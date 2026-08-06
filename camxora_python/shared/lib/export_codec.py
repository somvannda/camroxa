"""Video export codec labels for UI and MG_EVENT payloads."""

from __future__ import annotations

DEFAULT_EXPORT_SPEED_MODE = "fast"

_EXPORT_SPEED_CHOICES = frozenset(
    {"best_quality", "quality", "balanced", "fast", "very_fast"}
)


def normalize_export_speed_mode(value: object, *, default: str = DEFAULT_EXPORT_SPEED_MODE) -> str:
    mode = str(value or default).strip().lower()
    if mode in {"master", "best"}:
        mode = "best_quality"
    if mode in _EXPORT_SPEED_CHOICES:
        return mode
    return default if default in _EXPORT_SPEED_CHOICES else "fast"


def export_video_codec_label(codec: object) -> str:
    """Human label for ffmpeg video codec id (e.g. h264_nvenc → NVENC)."""
    text = str(codec or "").strip().lower()
    if not text:
        return ""
    if "nvenc" in text:
        return "NVENC"
    if text in {"libx264", "h264"} or "x264" in text:
        return "CPU x264"
    return text


def format_export_status_message(message: str, *, video_codec: object = None) -> str:
    """Append codec badge once when encoder is known."""
    base = str(message or "").strip() or "Exporting…"
    label = export_video_codec_label(video_codec)
    if not label:
        return base
    if label in base:
        return base
    return f"{base} · {label}"
