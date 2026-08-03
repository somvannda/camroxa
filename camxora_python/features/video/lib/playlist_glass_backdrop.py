"""Backdrop-sampled frost for Playlist glass panels.

Crops a region from the static background image, blurs it, and returns an
RGBA plate the same size as the panel. Approximate (not post-scene GPU blur),
but reads as real frosted glass on busy stills.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def sample_panel_backdrop_rgba(
    background_path: str,
    *,
    panel_w: int,
    panel_h: int,
    rel_x: float = 0.35,
    rel_y: float = 0.45,
    blur_radius: float = 16.0,
) -> np.ndarray | None:
    """Return HxWx4 uint8 crop (panel_h x panel_w), or None on failure."""
    path = str(background_path or "").strip()
    if not path or not Path(path).is_file():
        return None
    pw = int(max(4, min(2048, panel_w)))
    ph = int(max(4, min(2048, panel_h)))
    try:
        from PIL import Image, ImageFilter

        src = Image.open(path).convert("RGBA")
    except Exception:
        return None
    sw, sh = src.size
    if sw < 4 or sh < 4:
        return None
    # Cover-scale so we can crop a panel-sized window.
    scale = max(pw / float(sw), ph / float(sh), 1.0)
    # Prefer oversampling for nicer blur.
    scale = max(scale, (pw * 1.35) / float(sw), (ph * 1.35) / float(sh))
    nw = max(pw, int(round(sw * scale)))
    nh = max(ph, int(round(sh * scale)))
    try:
        fitted = src.resize((nw, nh), Image.Resampling.LANCZOS)
    except Exception:
        fitted = src.resize((nw, nh))
    rx = float(max(0.0, min(1.0, rel_x)))
    ry = float(max(0.0, min(1.0, rel_y)))
    max_x = max(0, nw - pw)
    max_y = max(0, nh - ph)
    x0 = int(round(max_x * rx))
    y0 = int(round(max_y * ry))
    crop = fitted.crop((x0, y0, x0 + pw, y0 + ph))
    radius = int(max(2, min(48, round(float(blur_radius)))))
    try:
        crop = crop.filter(ImageFilter.GaussianBlur(radius=radius))
    except Exception:
        pass
    arr = np.array(crop.convert("RGBA"), dtype=np.uint8)
    if arr.shape[0] != ph or arr.shape[1] != pw:
        return None
    return arr


def panel_rel_from_overlay(
    overlay: dict[str, Any],
    *,
    frame_w: float = 800.0,
    frame_h: float = 450.0,
) -> tuple[float, float]:
    """Map overlay template x/y to 0..1 crop anchors (rough but stable)."""
    x = float(overlay.get("x", 0.0) or 0.0)
    y = float(overlay.get("y", 0.0) or 0.0)
    # Template offsets are often relative to center; shift into 0..1.
    rel_x = 0.5 + (x / max(80.0, float(frame_w)))
    rel_y = 0.5 - (y / max(80.0, float(frame_h)))
    return (float(max(0.05, min(0.95, rel_x))), float(max(0.05, min(0.95, rel_y))))
