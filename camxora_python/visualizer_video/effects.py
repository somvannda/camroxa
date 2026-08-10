from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import pygame


def _get_pygame() -> "pygame":
    import pygame as _pygame
    return _pygame


@dataclass(frozen=True)
class BloomConfig:
    enabled: bool
    strength: float
    blur_radius: int
    threshold: float
    opacity: float


@dataclass(frozen=True)
class RgbSplitConfig:
    enabled: bool
    red_offset: tuple[int, int]
    green_offset: tuple[int, int]
    blue_offset: tuple[int, int]
    opacity: float


def _surface_to_bgr(surface: "pygame.Surface") -> np.ndarray:
    pg = _get_pygame()
    arr = pg.surfarray.array3d(surface)
    arr = np.transpose(arr, (1, 0, 2))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _bgr_to_surface(bgr: np.ndarray) -> "pygame.Surface":
    pg = _get_pygame()
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = np.transpose(rgb, (1, 0, 2))
    return pg.surfarray.make_surface(rgb)


def apply_bloom(surface: "pygame.Surface", cfg: BloomConfig) -> "pygame.Surface":
    if not cfg.enabled:
        return surface
    bgr = _surface_to_bgr(surface)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    thresh_val = int(max(0.0, min(1.0, cfg.threshold)) * 255.0)
    _, mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
    glow = cv2.bitwise_and(bgr, bgr, mask=mask)

    k = int(max(1, cfg.blur_radius))
    if k % 2 == 0:
        k += 1
    glow_blur = cv2.GaussianBlur(glow, (k, k), 0)

    strength = float(cfg.strength)
    opacity = float(cfg.opacity)
    opacity = max(0.0, min(1.0, opacity))
    out = cv2.addWeighted(bgr, 1.0, glow_blur, strength * opacity, 0.0)
    return _bgr_to_surface(out)


def apply_rgb_split(surface: "pygame.Surface", cfg: RgbSplitConfig) -> "pygame.Surface":
    if not cfg.enabled:
        return surface
    bgr = _surface_to_bgr(surface)
    h, w = bgr.shape[:2]
    b, g, r = cv2.split(bgr)

    def shift(ch: np.ndarray, dx: int, dy: int) -> np.ndarray:
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(ch, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    rx, ry = cfg.red_offset
    gx, gy = cfg.green_offset
    bx, by = cfg.blue_offset

    r2 = shift(r, int(rx), int(ry))
    g2 = shift(g, int(gx), int(gy))
    b2 = shift(b, int(bx), int(by))
    merged = cv2.merge([b2, g2, r2])

    opacity = float(cfg.opacity)
    opacity = max(0.0, min(1.0, opacity))
    out = cv2.addWeighted(bgr, 1.0 - opacity, merged, opacity, 0.0)
    return _bgr_to_surface(out)

