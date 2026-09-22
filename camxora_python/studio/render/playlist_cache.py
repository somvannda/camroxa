"""Caches for playlist preview — backgrounds and static card layers."""

from __future__ import annotations

import functools
import os
from typing import Any

import cv2
import numpy as np

from studio.core.playlist_settings import PlaylistSettings
from studio.render.compositor import _load_image_rgb


@functools.lru_cache(maxsize=24)
def cached_background_cover(path: str, width: int, height: int, mtime_ns: int) -> np.ndarray | None:
    """Load and cover-fit a background image (cached by path + size + mtime)."""
    del mtime_ns  # part of cache key only
    frame = _load_image_rgb(path)
    if frame is None:
        return None
    ih, iw = frame.shape[:2]
    if ih <= 0 or iw <= 0:
        return None
    scale = max(width / iw, height / ih)
    nw = max(1, int(round(iw * scale)))
    nh = max(1, int(round(ih * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(frame, (nw, nh), interpolation=interp)
    x0 = max(0, (nw - width) // 2)
    y0 = max(0, (nh - height) // 2)
    crop = resized[y0 : y0 + height, x0 : x0 + width]
    if crop.shape[0] != height or crop.shape[1] != width:
        return None
    return crop.copy()


def background_mtime_ns(path: str | None) -> int:
    if not path:
        return 0
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return 0


def playlist_background_key(
    width: int,
    height: int,
    bg_path: str | None,
    bg_from: str,
    bg_to: str,
) -> tuple[Any, ...]:
    return (
        width,
        height,
        bg_path or "",
        background_mtime_ns(bg_path),
        bg_from,
        bg_to,
    )


def playlist_media_fingerprint(project_state, song_ids: tuple[str, ...] | list[str]) -> tuple[tuple[str, str, float], ...]:
    """Stable row labels for static card cache invalidation."""
    parts: list[tuple[str, str, float]] = []
    for media_id in song_ids:
        media = project_state.get_media(media_id)
        if media is None:
            parts.append((media_id, "", 0.0))
            continue
        parts.append((media_id, media.name, round(float(media.duration or 0), 2)))
    return tuple(parts)


def playlist_static_card_key(
    settings: PlaylistSettings,
    width: int,
    height: int,
    card_rect: tuple[int, int, int, int],
    colors: dict[str, str],
    media_fingerprint: tuple[tuple[str, str, float], ...],
) -> tuple[Any, ...]:
    x, y, w, h = card_rect
    typo = settings.typography
    return (
        width,
        height,
        x,
        y,
        w,
        h,
        settings.sub_template_id,
        settings.color_filter_id,
        settings.list_side,
        tuple(settings.song_ids),
        media_fingerprint,
        settings.corner_radius,
        tuple(sorted(settings.row_chrome.to_dict().items())),
        settings.list_row_gap,
        typo.song_title_size,
        typo.song_meta_size,
        typo.font_family,
        typo.song_title_variant,
        typo.song_meta_variant,
        tuple(sorted(colors.items())),
    )


def playlist_card_shadow_key(w: int, h: int, radius: int, shadow_hex: str) -> tuple[Any, ...]:
    return (w, h, radius, shadow_hex)


class PlaylistRenderCache:
    """Process-wide cache for expensive playlist layers."""

    def __init__(self) -> None:
        self._background_key: tuple[Any, ...] | None = None
        self._background: np.ndarray | None = None
        self._static_key: tuple[Any, ...] | None = None
        self._static_card: np.ndarray | None = None
        self._shadow_key: tuple[Any, ...] | None = None
        self._shadow_rgba: np.ndarray | None = None

    def clear(self) -> None:
        self._background_key = None
        self._background = None
        self._static_key = None
        self._static_card = None
        self._shadow_key = None
        self._shadow_rgba = None
        cached_background_cover.cache_clear()

    def get_background(self, key: tuple[Any, ...], builder) -> np.ndarray:
        if self._background_key != key or self._background is None:
            self._background = builder()
            self._background_key = key
        return self._background

    def get_static_card(self, key: tuple[Any, ...], builder) -> np.ndarray:
        if self._static_key != key or self._static_card is None:
            self._static_card = builder()
            self._static_key = key
        return self._static_card

    def get_card_shadow(self, key: tuple[Any, ...], builder) -> np.ndarray:
        if self._shadow_key != key or self._shadow_rgba is None:
            self._shadow_rgba = builder()
            self._shadow_key = key
        return self._shadow_rgba


_CACHE = PlaylistRenderCache()


def playlist_render_cache() -> PlaylistRenderCache:
    return _CACHE


def invalidate_playlist_render_cache() -> None:
    _CACHE.clear()
