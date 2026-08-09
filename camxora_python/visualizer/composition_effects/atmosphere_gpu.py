"""Atmosphere GPU draw helpers — Session B weather/volume (≠ particle emitters)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from visualizer.scene import NONE


def build_atmosphere_draw(atmosphere: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize atmosphereSettings into a compact GPU draw descriptor."""
    if not isinstance(atmosphere, dict) or not bool(atmosphere.get("enabled")):
        return None
    aid = str(atmosphere.get("atmosphereId") or NONE)
    if aid in ("", NONE, "none"):
        return None
    draw = atmosphere.get("draw") if isinstance(atmosphere.get("draw"), dict) else {}
    kind = str(draw.get("kind") or "volume")
    density = float(draw.get("density") or 0.35)
    density = max(0.05, min(1.0, density))
    tint_hex = str(draw.get("tint") or "#a8b4c8")
    speed = float(draw.get("speed") or 1.0)
    return {
        "enabled": True,
        "atmosphereId": aid,
        "kind": kind,
        "density": density,
        "tint": tint_hex,
        "speed": max(0.05, min(3.0, speed)),
        "twinkle": float(draw.get("twinkle") or 0.0),
        "amplitude": float(draw.get("amplitude") or 0.0),
        "flash": float(draw.get("flash") or 0.0),
        "caustics": float(draw.get("caustics") or 0.0),
    }


def _hex_rgba(hex_color: str, alpha: float) -> tuple[float, float, float, float]:
    text = str(hex_color or "#ffffff").strip().lstrip("#")
    if len(text) >= 6:
        try:
            r = int(text[0:2], 16) / 255.0
            g = int(text[2:4], 16) / 255.0
            b = int(text[4:6], 16) / 255.0
            return (r, g, b, float(max(0.0, min(1.0, alpha))))
        except ValueError:
            pass
    return (0.65, 0.7, 0.78, float(max(0.0, min(1.0, alpha))))


def atmosphere_fog_quad(rgba: tuple[float, float, float, float]) -> np.ndarray:
    """Two triangles covering NDC for a soft volume wash."""
    r, g, b, a = rgba
    # Slightly stronger at edges via duplicated verts with same color (post vignette also helps).
    corners = np.array(
        [
            [-1.0, -1.0, r, g, b, a],
            [1.0, -1.0, r, g, b, a],
            [1.0, 1.0, r, g, b, a],
            [-1.0, -1.0, r, g, b, a],
            [1.0, 1.0, r, g, b, a],
            [-1.0, 1.0, r, g, b, a],
        ],
        dtype=np.float32,
    )
    return corners


def atmosphere_weather_segments(
    *,
    kind: str,
    density: float,
    speed: float,
    tint: str,
    time_sec: float,
    width: int,
    height: int,
) -> np.ndarray:
    """Build line-strip segments for rain/snow/storm (NDC + RGBA)."""
    w = max(1, int(width))
    h = max(1, int(height))
    t = float(time_sec)
    count = int(40 + density * (220 if kind in {"rain", "storm"} else 160))
    count = max(20, min(400, count))
    is_snow = kind == "snow"
    streak = 0.045 if kind == "storm" else (0.03 if kind == "rain" else 0.012)
    fall = (1.6 if kind == "storm" else (1.2 if kind == "rain" else 0.35)) * speed
    wind = 0.08 if kind == "storm" else (0.02 if kind == "rain" else 0.01)
    alpha = 0.55 * density if not is_snow else 0.7 * density
    rgba = _hex_rgba("#dbeafe" if not is_snow else "#f8fafc", alpha)
    r, g, b, a = rgba

    verts = np.empty((count * 2, 6), dtype=np.float32)
    for i in range(count):
        # Stable pseudo-random layout per index.
        seed = (i * 1103515245 + 12345) & 0x7FFFFFFF
        x0 = ((seed % 10007) / 10007.0) * 2.0 - 1.0
        y_phase = ((seed // 10007) % 10007) / 10007.0
        y = ((y_phase + t * fall * 0.25) % 1.0) * 2.0 - 1.0
        x = x0 + wind * math.sin(t * 1.3 + i * 0.17)
        # Aspect-correct streak length.
        dy = streak * (h / max(w, 1)) * (0.6 if is_snow else 1.0)
        dx = wind * streak * (0.2 if is_snow else 1.0)
        verts[i * 2 + 0] = (x, y, r, g, b, a)
        verts[i * 2 + 1] = (x + dx, y - dy, r, g, b, a * 0.35)
    return verts


def atmosphere_star_points(
    *,
    density: float,
    twinkle: float,
    time_sec: float,
) -> np.ndarray:
    """Point sprites for stars/nebula (x, y, size)."""
    count = int(30 + density * 120)
    count = max(16, min(220, count))
    t = float(time_sec)
    out = np.empty((count, 3), dtype=np.float32)
    for i in range(count):
        seed = (i * 1664525 + 1013904223) & 0x7FFFFFFF
        x = ((seed % 10007) / 10007.0) * 2.0 - 1.0
        y = (((seed // 10007) % 10007) / 10007.0) * 2.0 - 1.0
        base = 1.5 + (seed % 5)
        tw = 1.0 + twinkle * 0.5 * math.sin(t * 3.0 + i)
        out[i] = (x, y, base * tw)
    return out
