"""Shared timeline layout constants (ports of the reference CSS/JS numbers)."""

from __future__ import annotations

RULER_HEIGHT = 30
MINIMAP_HEIGHT = 24
TRACK_HEIGHT = 56
TRACK_HEADER_WIDTH = 200
MIN_VISIBLE_TRACK_ROWS = 1
EXTRA_DROP_ROW = 1  # one generic empty row at the bottom when tracks exist

CLIP_VERTICAL_MARGIN = 3
CLIP_HEIGHT = TRACK_HEIGHT - CLIP_VERTICAL_MARGIN * 2
CLIP_LABEL_HEIGHT = 11
CLIP_TYPE_STRIP_WIDTH = 16
HANDLE_WIDTH_PX = 10
HANDLE_HOVER_WIDTH_PX = 14
MIN_CONTENT_WIDTH_PX = 1200
TIMELINE_PAD_SECONDS = 20
MIN_CLIP_WIDTH_PX = 14
MIN_PX_PER_SEC = 1.0
MAX_PX_PER_SEC = 220.0
DEFAULT_PX_PER_SEC = 70.0
ZOOM_DEBOUNCE_MS = 50
VIEWPORT_CULL_BUFFER_X_RATIO = 0.5
VIEWPORT_CULL_BUFFER_ROWS = 2
LANE_STRIPE_WIDTH = 3
FILMSTRIP_THUMB_WIDTH_PX = 42
TRACK_BADGE_SIZE = 22
TRACK_BADGE_ICON_PX = 9

TRACK_ACCENT = {"video": "#7c5cff", "audio": "#26d6a4", "overlay": "#ffb648"}
TRACK_LANE_BG = ("#0e0e14", "#12121a")
EMPTY_LANE_HINT_GENERIC = "Drop media here"


def visible_track_rows(track_count: int) -> int:
    """Only real tracks + at most one generic drop row — no pre-typed lane grid."""
    if track_count == 0:
        return MIN_VISIBLE_TRACK_ROWS
    return track_count + EXTRA_DROP_ROW


def timeline_width_px(duration: float, px_per_sec: float) -> float:
    return max(MIN_CONTENT_WIDTH_PX, (duration + TIMELINE_PAD_SECONDS) * px_per_sec)


def effective_timeline_width_px(duration: float, px_per_sec: float, viewport_width: float) -> float:
    """Content width, but never narrower than the visible timeline viewport."""
    content = timeline_width_px(duration, px_per_sec)
    if viewport_width <= 0:
        return content
    return max(content, viewport_width)


def ruler_step_seconds(px_per_sec: float) -> float:
    if px_per_sec < 2:
        return 300.0  # 5 min — hour-scale timelines
    if px_per_sec < 5:
        return 60.0
    if px_per_sec < 15:
        return 30.0
    if px_per_sec < 40:
        return 10.0
    if px_per_sec < 90:
        return 5.0
    if px_per_sec < 160:
        return 2.0
    return 1.0


def ruler_sub_step_seconds(px_per_sec: float, frame_rate: float = 30.0) -> float | None:
    """Minor tick interval at high zoom — uses project frame rate when zoomed in."""
    fps = max(1.0, frame_rate)
    frame_sec = 1.0 / fps
    if px_per_sec >= 200:
        return frame_sec
    if px_per_sec >= 120:
        return frame_sec * 2
    if px_per_sec >= 80:
        return 1.0
    if px_per_sec >= 30:
        return 5.0
    if px_per_sec >= 10:
        return 10.0
    if px_per_sec >= 3:
        return 30.0
    return None


def filmstrip_slot_width_px(px_per_sec: float) -> float:
    """LOD tile width — compact when zoomed out, wider when zoomed in."""
    if px_per_sec < 15:
        return 24.0
    if px_per_sec < 40:
        return 32.0
    if px_per_sec < 90:
        return float(FILMSTRIP_THUMB_WIDTH_PX)
    return min(72.0, FILMSTRIP_THUMB_WIDTH_PX * 1.25)


def filmstrip_frame_stride(px_per_sec: float, thumb_count: int) -> int:
    """When zoomed out, tile every Nth cached frame instead of all frames."""
    if thumb_count <= 1:
        return 1
    if px_per_sec >= 60:
        return 1
    if px_per_sec >= 25:
        return max(1, thumb_count // 6)
    return max(1, thumb_count // 3)


def waveform_sample_count(body_width_px: float, px_per_sec: float) -> int:
    """LOD waveform resolution — fewer samples when zoomed out."""
    base = max(8, min(180, int(body_width_px / 1.5)))
    if px_per_sec < 8:
        return min(base, 20)
    if px_per_sec < 25:
        return min(base, 40)
    if px_per_sec < 60:
        return min(base, 80)
    return base


def hi_dpi_filmstrip_size(base_size: tuple[int, int], device_pixel_ratio: float) -> tuple[int, int]:
    dpr = max(1.0, device_pixel_ratio)
    return (max(1, int(base_size[0] * dpr)), max(1, int(base_size[1] * dpr)))


def zoom_wheel_step(px_per_sec: float) -> float:
    """Ctrl+wheel zoom increment — smaller steps when zoomed far out."""
    if px_per_sec <= 5:
        return 0.5
    if px_per_sec <= 20:
        return 1.0
    if px_per_sec <= 50:
        return 2.0
    return 8.0
