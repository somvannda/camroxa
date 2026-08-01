"""Procedural music-icon atlas for particle style ``music``."""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

MUSIC_ICON_COUNT = 4
ICON_CELL = 128


def _blank(cell: int) -> np.ndarray:
    return np.zeros((cell, cell, 4), dtype=np.uint8)


def _stamp_disk(img: np.ndarray, cx: float, cy: float, radius: float, alpha: float = 1.0) -> None:
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    edge = np.clip((radius + 1.2 - d) / 1.2, 0.0, 1.0) * float(alpha)
    for c in range(3):
        img[:, :, c] = np.maximum(img[:, :, c], (edge * 255.0).astype(np.uint8))
    img[:, :, 3] = np.maximum(img[:, :, 3], (edge * 255.0).astype(np.uint8))


def _stamp_line(
    img: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    thickness: float,
    alpha: float = 1.0,
) -> None:
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy) or 1.0
    px = (xx - x0) * dx / length + (yy - y0) * dy / length
    py = (xx - x0) * (-dy) / length + (yy - y0) * dx / length
    along = (px >= -0.5) & (px <= length + 0.5)
    across = np.abs(py) <= thickness
    edge = np.clip((thickness + 0.8 - np.abs(py)) / 0.8, 0.0, 1.0)
    mask = along & across
    val = (edge * float(alpha) * 255.0).astype(np.uint8)
    for c in range(3):
        img[:, :, c] = np.where(mask, np.maximum(img[:, :, c], val), img[:, :, c])
    img[:, :, 3] = np.where(mask, np.maximum(img[:, :, 3], val), img[:, :, 3])


def _draw_eighth(cell: int) -> np.ndarray:
    img = _blank(cell)
    s = cell / 128.0
    _stamp_disk(img, 48 * s, 88 * s, 16 * s)
    _stamp_line(img, 62 * s, 88 * s, 62 * s, 28 * s, 3.2 * s)
    # flag
    _stamp_line(img, 62 * s, 28 * s, 92 * s, 42 * s, 3.0 * s)
    _stamp_line(img, 92 * s, 42 * s, 78 * s, 58 * s, 2.6 * s)
    return img


def _draw_beamed(cell: int) -> np.ndarray:
    img = _blank(cell)
    s = cell / 128.0
    _stamp_disk(img, 36 * s, 90 * s, 13 * s)
    _stamp_disk(img, 82 * s, 90 * s, 13 * s)
    _stamp_line(img, 48 * s, 90 * s, 48 * s, 34 * s, 2.8 * s)
    _stamp_line(img, 94 * s, 90 * s, 94 * s, 34 * s, 2.8 * s)
    _stamp_line(img, 48 * s, 34 * s, 94 * s, 34 * s, 4.0 * s)
    _stamp_line(img, 48 * s, 44 * s, 94 * s, 44 * s, 3.2 * s)
    return img


def _draw_quarter(cell: int) -> np.ndarray:
    img = _blank(cell)
    s = cell / 128.0
    _stamp_disk(img, 52 * s, 86 * s, 17 * s)
    _stamp_line(img, 68 * s, 86 * s, 68 * s, 26 * s, 3.4 * s)
    return img


def _draw_treble_simple(cell: int) -> np.ndarray:
    """Simplified treble-like swirl (procedural, font-free)."""
    img = _blank(cell)
    s = cell / 128.0
    cx, cy = 64 * s, 64 * s
    for i in range(48):
        t = i / 47.0
        ang = t * math.pi * 3.2 + 0.4
        rad = (10 + t * 38) * s
        x = cx + math.cos(ang) * rad * 0.55
        y = cy + math.sin(ang) * rad - 8 * s
        _stamp_disk(img, x, y, (3.2 - t * 1.2) * s, alpha=0.95)
    _stamp_disk(img, cx + 6 * s, cy + 34 * s, 8 * s)
    _stamp_line(img, cx + 2 * s, cy - 40 * s, cx + 2 * s, cy + 42 * s, 2.8 * s)
    return img


@lru_cache(maxsize=1)
def build_music_icon_atlas(*, cell: int = ICON_CELL) -> tuple[np.ndarray, int]:
    """Return ``(H, W, 4) uint8`` atlas and icon count. Row of icons left-to-right."""
    drawers = (_draw_eighth, _draw_beamed, _draw_quarter, _draw_treble_simple)
    tiles = [fn(cell) for fn in drawers]
    atlas = np.concatenate(tiles, axis=1)
    return atlas, len(tiles)


def music_icon_uv_rect(icon_index: int, count: int = MUSIC_ICON_COUNT) -> tuple[float, float, float, float]:
    """Return ``(u0, v0, u1, v1)`` in atlas space for one icon cell."""
    n = max(1, int(count))
    i = int(icon_index) % n
    u0 = float(i) / float(n)
    u1 = float(i + 1) / float(n)
    return u0, 0.0, u1, 1.0
