"""Atmosphere GPU draw helpers — Session B weather/volume (≠ particle emitters)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from visualizer_studio.scene import NONE


def build_atmosphere_draw(atmosphere: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize atmosphereSettings into a compact GPU draw descriptor."""
    if not isinstance(atmosphere, dict) or not bool(atmosphere.get("enabled")):
        return None
    aid = str(atmosphere.get("atmosphereId") or NONE)
    if aid in ("", NONE, "none"):
        return None
    draw = atmosphere.get("draw") if isinstance(atmosphere.get("draw"), dict) else {}
    kind = str(draw.get("kind") or "volume")
    try:
        density = max(0.0, min(2.5, float(draw.get("density") or 0.35)))
    except (TypeError, ValueError):
        density = 0.35
    try:
        speed = max(0.05, min(4.0, float(draw.get("speed") or 1.0)))
    except (TypeError, ValueError):
        speed = 1.0
    try:
        opacity = max(0.0, min(1.0, float(draw.get("opacity") or 1.0)))
    except (TypeError, ValueError):
        opacity = 1.0
    try:
        wind = max(0.0, min(3.0, float(draw.get("wind") or 1.0)))
    except (TypeError, ValueError):
        wind = 1.0
    if density <= 0.001 or opacity <= 0.001:
        return None
    return {
        "enabled": True,
        "atmosphereId": aid,
        "kind": kind,
        "density": density,
        "tint": str(draw.get("tint") or "#a8b4c8"),
        "speed": speed,
        "opacity": opacity,
        "wind": wind,
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


def _wrap01(value: float) -> float:
    return value - math.floor(value)


def atmosphere_fog_quad(rgba: tuple[float, float, float, float]) -> np.ndarray:
    """Two triangles covering NDC for a soft volume wash."""
    r, g, b, a = rgba
    return np.array(
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


def atmosphere_weather_segments(
    *,
    kind: str,
    density: float,
    speed: float,
    tint: str,
    time_sec: float,
    width: int,
    height: int,
    wind: float = 1.0,
    opacity: float = 1.0,
) -> np.ndarray:
    """Build line segments for rain/snow/storm.

    NDC Y increases upward, so falling weather must *decrease* Y over time.
    """
    w = max(1, int(width))
    h = max(1, int(height))
    t = float(time_sec)
    weather = str(kind or "rain")
    dens = max(0.0, float(density))
    op = max(0.0, min(1.0, float(opacity)))
    # Density drives drop count; opacity drives streak alpha (don't kill drops via density).
    count = int(round(dens * (280 if weather in {"rain", "storm"} else 200)))
    count = max(0, min(420, count))
    if count <= 0 or op <= 0.001:
        return np.empty((0, 6), dtype=np.float32)
    is_snow = weather == "snow"
    streak = 0.05 if weather == "storm" else (0.034 if weather == "rain" else 0.014)
    # Positive fall_rate → downward travel in NDC.
    fall = (1.85 if weather == "storm" else (1.35 if weather == "rain" else 0.42)) * max(0.05, speed)
    wind_amt = (0.11 if weather == "storm" else (0.035 if weather == "rain" else 0.02)) * max(0.0, wind)
    alpha = (0.72 if not is_snow else 0.85) * op
    default_tint = "#dbeafe" if not is_snow else "#f8fafc"
    rgba = _hex_rgba(str(tint or default_tint), alpha)
    r, g, b, a = rgba

    verts = np.empty((count * 2, 6), dtype=np.float32)
    for i in range(count):
        seed = (i * 1103515245 + 12345) & 0x7FFFFFFF
        x0 = ((seed % 10007) / 10007.0) * 2.0 - 1.0
        y_phase = ((seed // 10007) % 10007) / 10007.0
        # Fall down: subtract time so Y decreases.
        y = _wrap01(y_phase - t * fall * 0.28) * 2.0 - 1.0
        x = x0 + wind_amt * math.sin(t * 1.35 + i * 0.17)
        dy = streak * (h / max(w, 1)) * (0.55 if is_snow else 1.0)
        dx = wind_amt * streak * (0.35 if is_snow else 1.15)
        # Head (higher) → tip (lower) so streaks read as falling.
        verts[i * 2 + 0] = (x, y + dy, r, g, b, a * 0.35)
        verts[i * 2 + 1] = (x + dx, y, r, g, b, a)
    return verts


def atmosphere_star_points(
    *,
    density: float,
    twinkle: float,
    time_sec: float,
) -> np.ndarray:
    """Point sprites for stars/nebula (x, y, size)."""
    count = int(30 + density * 140)
    count = max(16, min(240, count))
    t = float(time_sec)
    out = np.empty((count, 3), dtype=np.float32)
    for i in range(count):
        seed = (i * 1664525 + 1013904223) & 0x7FFFFFFF
        x = ((seed % 10007) / 10007.0) * 2.0 - 1.0
        y = (((seed // 10007) % 10007) / 10007.0) * 2.0 - 1.0
        base = 1.5 + (seed % 5)
        tw = 1.0 + twinkle * 0.55 * math.sin(t * 3.0 + i)
        out[i] = (x, y, base * tw)
    return out


def atmosphere_dust_points(
    *,
    density: float,
    speed: float,
    time_sec: float,
    wind: float = 1.0,
) -> np.ndarray:
    """Slow drifting motes for dust/smoke/haze."""
    count = int(24 + density * 110)
    count = max(12, min(180, count))
    t = float(time_sec)
    out = np.empty((count, 3), dtype=np.float32)
    for i in range(count):
        seed = (i * 214013 + 2531011) & 0x7FFFFFFF
        x0 = ((seed % 10007) / 10007.0) * 2.0 - 1.0
        y0 = (((seed // 10007) % 10007) / 10007.0) * 2.0 - 1.0
        x = ((x0 + 1.0) * 0.5 + t * 0.03 * speed * max(0.15, wind)) % 1.0 * 2.0 - 1.0
        y = ((y0 + 1.0) * 0.5 + 0.02 * math.sin(t * 0.7 * speed + i)) % 1.0 * 2.0 - 1.0
        size = 1.2 + (seed % 4) * 0.55
        out[i] = (x, y, size)
    return out


def atmosphere_cloud_bands(
    *,
    density: float,
    speed: float,
    tint: str,
    time_sec: float,
    opacity: float = 1.0,
) -> np.ndarray:
    """Soft horizontal cloud slabs drifting sideways."""
    bands = max(3, min(10, int(3 + density * 5)))
    t = float(time_sec)
    rgba = _hex_rgba(tint, (0.08 + 0.14 * density) * max(0.05, min(1.0, opacity)))
    r, g, b, a = rgba
    verts: list[list[float]] = []
    for i in range(bands):
        y = -0.85 + i * (1.7 / max(1, bands - 1))
        y += 0.04 * math.sin(t * 0.25 * speed + i)
        x_shift = 0.35 * math.sin(t * 0.12 * speed + i * 0.7)
        half_w = 0.55 + 0.2 * ((i * 37) % 5) / 5.0
        half_h = 0.05 + 0.03 * (i % 3)
        x0, x1 = x_shift - half_w, x_shift + half_w
        y0, y1 = y - half_h, y + half_h
        verts.extend(
            [
                [x0, y0, r, g, b, a],
                [x1, y0, r, g, b, a],
                [x1, y1, r, g, b, a * 0.55],
                [x0, y0, r, g, b, a],
                [x1, y1, r, g, b, a * 0.55],
                [x0, y1, r, g, b, a * 0.7],
            ]
        )
    return np.asarray(verts, dtype=np.float32)


def atmosphere_aurora_ribbons(
    *,
    density: float,
    speed: float,
    tint: str,
    time_sec: float,
    opacity: float = 1.0,
) -> np.ndarray:
    """Vertical aurora ribbons (line strips)."""
    ribbons = max(4, min(14, int(4 + density * 8)))
    t = float(time_sec)
    rgba = _hex_rgba(tint, (0.35 + 0.4 * density) * max(0.05, min(1.0, opacity)))
    r, g, b, a = rgba
    segs_per = 18
    verts = np.empty((ribbons * (segs_per - 1) * 2, 6), dtype=np.float32)
    idx = 0
    for i in range(ribbons):
        x_base = -0.9 + (i + 0.5) * (1.8 / ribbons)
        for s in range(segs_per - 1):
            y0 = -0.2 + s / (segs_per - 1) * 1.15
            y1 = -0.2 + (s + 1) / (segs_per - 1) * 1.15
            wave0 = 0.08 * math.sin(t * 1.1 * speed + i + s * 0.35)
            wave1 = 0.08 * math.sin(t * 1.1 * speed + i + (s + 1) * 0.35)
            fade = 0.35 + 0.65 * (s / max(1, segs_per - 2))
            verts[idx] = (x_base + wave0, y0, r, g, b, a * fade * 0.55)
            verts[idx + 1] = (x_base + wave1, y1, r, g, b, a * fade)
            idx += 2
    return verts[:idx]


def atmosphere_heat_shimmer(
    *,
    density: float,
    speed: float,
    amplitude: float,
    time_sec: float,
    opacity: float = 1.0,
) -> np.ndarray:
    """Horizontal shimmer lines for heatwave."""
    lines = max(8, min(28, int(8 + density * 16)))
    t = float(time_sec)
    amp = max(0.01, min(0.12, float(amplitude) if amplitude else 0.03))
    rgba = _hex_rgba("#fde68a", (0.1 + 0.2 * density) * max(0.05, min(1.0, opacity)))
    r, g, b, a = rgba
    verts = np.empty((lines * 2, 6), dtype=np.float32)
    for i in range(lines):
        y = -0.95 + (i + 0.5) * (1.9 / lines)
        phase = t * 2.2 * speed + i * 0.4
        x0 = -1.0 + amp * math.sin(phase)
        x1 = 1.0 + amp * math.sin(phase + 0.8)
        verts[i * 2] = (x0, y, r, g, b, a * 0.45)
        verts[i * 2 + 1] = (x1, y + 0.01 * math.sin(phase), r, g, b, a)
    return verts


def atmosphere_caustic_points(
    *,
    density: float,
    speed: float,
    time_sec: float,
) -> np.ndarray:
    """Underwater caustic sparkles."""
    count = int(20 + density * 90)
    count = max(12, min(160, count))
    t = float(time_sec)
    out = np.empty((count, 3), dtype=np.float32)
    for i in range(count):
        seed = (i * 1103515245 + 12345) & 0x7FFFFFFF
        x = ((seed % 10007) / 10007.0) * 2.0 - 1.0
        y = (((seed // 10007) % 10007) / 10007.0) * 2.0 - 1.0
        x += 0.08 * math.sin(t * 1.4 * speed + i)
        y += 0.05 * math.cos(t * 1.1 * speed + i * 0.3)
        pulse = 1.0 + 0.8 * abs(math.sin(t * 2.5 * speed + i))
        out[i] = (x, y, (1.0 + seed % 3) * pulse)
    return out
