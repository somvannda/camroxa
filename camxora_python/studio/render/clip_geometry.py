"""Shared clip placement math for compositor + preview overlay."""

from __future__ import annotations

import logging

import numpy as np

from studio.core.models import Clip
from studio.core.time_utils import clamp

logger = logging.getLogger(__name__)

IMAGE_FIT_MODES: tuple[str, ...] = ("fit", "cover", "fill")
MAX_TILE_DIMENSION = 8192


def clip_source_size(
    clip: Clip, frame: np.ndarray | None = None, *, fallback_w: int = 0, fallback_h: int = 0
) -> tuple[int, int]:
    if frame is not None:
        src_h, src_w = frame.shape[:2]
    elif fallback_w > 0 and fallback_h > 0:
        src_w, src_h = fallback_w, fallback_h
    else:
        return 0, 0
    inset = clamp(float(clip.crop_inset or 0.0), 0.0, 0.45)
    if inset <= 0.0:
        return src_w, src_h
    dx = int(round(src_w * inset))
    dy = int(round(src_h * inset))
    return max(1, src_w - 2 * dx), max(1, src_h - 2 * dy)


def _fit_base_scale(mode: str, src_w: int, src_h: int, canvas_w: int, canvas_h: int) -> float:
    if mode == "cover":
        return max(canvas_w / src_w, canvas_h / src_h)
    return min(canvas_w / src_w, canvas_h / src_h)


def _anchor_position(
    clip: Clip, dst_w: int, dst_h: int, canvas_w: int, canvas_h: int
) -> tuple[int, int]:
    anchor_x = clamp(float(clip.transform_x if clip.transform_x is not None else 0.5), 0.0, 1.0)
    anchor_y = clamp(float(clip.transform_y if clip.transform_y is not None else 0.5), 0.0, 1.0)
    x0 = int(round(anchor_x * canvas_w - dst_w / 2))
    y0 = int(round(anchor_y * canvas_h - dst_h / 2))
    return x0, y0


def _clamp_tile(w: int, h: int) -> tuple[int, int]:
    w = max(1, min(int(w), MAX_TILE_DIMENSION))
    h = max(1, min(int(h), MAX_TILE_DIMENSION))
    return w, h


def clip_dest_rect(clip: Clip, src_w: int, src_h: int, canvas_w: int, canvas_h: int) -> tuple[int, int, int, int]:
    """Return ``(x0, y0, dst_w, dst_h)`` in canvas pixel coordinates."""
    if src_w <= 0 or src_h <= 0 or canvas_w <= 0 or canvas_h <= 0:
        return 0, 0, 0, 0

    mode = clip.fit_mode if clip.fit_mode in IMAGE_FIT_MODES else "free"
    user_scale = clamp(float(clip.transform_scale or 1.0), 0.1, 5.0)

    if mode == "fill":
        dst_w, dst_h = _clamp_tile(canvas_w * user_scale, canvas_h * user_scale)
    else:
        base_scale = _fit_base_scale(mode, src_w, src_h, canvas_w, canvas_h)
        scale = base_scale * user_scale
        dst_w, dst_h = _clamp_tile(src_w * scale, src_h * scale)

    x0, y0 = _anchor_position(clip, dst_w, dst_h, canvas_w, canvas_h)
    logger.debug(
        "clip_dest_rect clip=%s mode=%s src=%sx%s canvas=%sx%s dst=%sx%s pos=(%s,%s) scale=%.3f",
        clip.id,
        mode,
        src_w,
        src_h,
        canvas_w,
        canvas_h,
        dst_w,
        dst_h,
        x0,
        y0,
        user_scale,
    )
    return x0, y0, dst_w, dst_h


def align_clip_transform(
    clip: Clip,
    alignment: str,
    src_w: int,
    src_h: int,
    canvas_w: int,
    canvas_h: int,
) -> tuple[float, float]:
    """Compute anchor ``(transform_x, transform_y)`` for canvas alignment."""
    x0, y0, dst_w, dst_h = clip_dest_rect(clip, src_w, src_h, canvas_w, canvas_h)
    tx = float(clip.transform_x if clip.transform_x is not None else 0.5)
    ty = float(clip.transform_y if clip.transform_y is not None else 0.5)

    if alignment == "left":
        tx = (dst_w / 2) / canvas_w
    elif alignment == "center_h":
        tx = 0.5
    elif alignment == "right":
        tx = (canvas_w - dst_w / 2) / canvas_w
    elif alignment == "top":
        ty = (dst_h / 2) / canvas_h
    elif alignment == "center_v":
        ty = 0.5
    elif alignment == "bottom":
        ty = (canvas_h - dst_h / 2) / canvas_h

    return clamp(tx, 0.0, 1.0), clamp(ty, 0.0, 1.0)


def distribute_selected_clips(
    project_state,
    axis: str,
    clips: list[Clip],
    canvas_w: int,
    canvas_h: int,
    frame_lookup,
) -> dict[str, tuple[float, float]]:
    """Evenly space clip centers along an axis. ``frame_lookup(clip)->(w,h)``."""
    if len(clips) < 2:
        return {}

    centers: list[tuple[str, float]] = []
    for clip in clips:
        src_w, src_h = frame_lookup(clip)
        if src_w <= 0 or src_h <= 0:
            continue
        x0, y0, dst_w, dst_h = clip_dest_rect(clip, src_w, src_h, canvas_w, canvas_h)
        cx = x0 + dst_w / 2
        cy = y0 + dst_h / 2
        centers.append((clip.id, cx if axis == "horizontal" else cy))

    if len(centers) < 2:
        return {}

    centers.sort(key=lambda item: item[1])
    min_pos = centers[0][1]
    max_pos = centers[-1][1]
    step = (max_pos - min_pos) / (len(centers) - 1) if len(centers) > 1 else 0.0

    updates: dict[str, tuple[float, float]] = {}
    for index, (clip_id, _old) in enumerate(centers):
        clip = next(c for c in clips if c.id == clip_id)
        src_w, src_h = frame_lookup(clip)
        _x0, _y0, dst_w, dst_h = clip_dest_rect(clip, src_w, src_h, canvas_w, canvas_h)
        target = min_pos + step * index
        if axis == "horizontal":
            tx = target / canvas_w
            ty = float(clip.transform_y if clip.transform_y is not None else 0.5)
        else:
            tx = float(clip.transform_x if clip.transform_x is not None else 0.5)
            ty = target / canvas_h
        updates[clip_id] = (clamp(tx, 0.0, 1.0), clamp(ty, 0.0, 1.0))
    return updates


def apply_crop(frame: np.ndarray, clip: Clip) -> np.ndarray:
    inset = clamp(float(clip.crop_inset or 0.0), 0.0, 0.45)
    if inset <= 0.0:
        return frame
    src_h, src_w = frame.shape[:2]
    dx = int(round(src_w * inset))
    dy = int(round(src_h * inset))
    x1, y1 = dx, dy
    x2, y2 = src_w - dx, src_h - dy
    if x2 <= x1 + 1 or y2 <= y1 + 1:
        return frame
    return frame[y1:y2, x1:x2]
