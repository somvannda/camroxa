"""Atmosphere descriptors — weather/fog/sky (Session B ≠ particle emitters)."""

from __future__ import annotations

from typing import Any

from visualizer.presets.atmosphere import normalize_atmosphere_id
from visualizer.scene import NONE

# Each style carries unique draw params (kind + tint + motion knobs).
_ATMOSPHERE_DRAW: dict[str, dict[str, Any]] = {
    "fog": {"kind": "volume", "density": 0.55, "tint": "#a8b4c8", "speed": 0.35, "opacity": 0.85},
    "mist": {"kind": "volume", "density": 0.3, "tint": "#d7dee8", "speed": 0.25, "opacity": 0.65},
    "rain": {"kind": "weather", "density": 0.7, "speed": 1.45, "tint": "#bfdbfe", "wind": 1.0, "opacity": 0.9},
    "snow": {"kind": "weather", "density": 0.45, "speed": 0.4, "tint": "#f8fafc", "wind": 0.6, "opacity": 0.95},
    "storm": {
        "kind": "weather",
        "density": 0.95,
        "speed": 1.9,
        "tint": "#93c5fd",
        "wind": 1.6,
        "flash": 0.45,
        "opacity": 1.0,
    },
    "stars": {"kind": "sky", "density": 0.55, "twinkle": 0.75, "tint": "#e2e8f0", "opacity": 0.9},
    "clouds": {"kind": "sky", "density": 0.5, "speed": 0.2, "tint": "#e5e7eb", "opacity": 0.75},
    "dust": {"kind": "volume", "density": 0.4, "tint": "#d2b48c", "speed": 0.45, "wind": 1.1, "opacity": 0.7},
    "smoke": {"kind": "volume", "density": 0.6, "tint": "#6b7280", "speed": 0.3, "wind": 0.7, "opacity": 0.8},
    "nebula": {"kind": "sky", "density": 0.65, "tint": "#7c3aed", "twinkle": 0.4, "speed": 0.25, "opacity": 0.85},
    "aurora": {"kind": "sky", "density": 0.6, "tint": "#22d3ee", "speed": 0.85, "opacity": 0.9},
    "haze": {"kind": "volume", "density": 0.28, "tint": "#e8dcc8", "speed": 0.2, "opacity": 0.55},
    "heatwave": {"kind": "distort", "density": 0.45, "amplitude": 0.035, "speed": 1.2, "opacity": 0.7},
    "underwater": {
        "kind": "volume",
        "density": 0.5,
        "tint": "#0e7490",
        "caustics": 0.65,
        "speed": 0.7,
        "opacity": 0.8,
    },
    "void": {"kind": "sky", "density": 0.95, "tint": "#020617", "twinkle": 0.15, "opacity": 0.95},
}


def build_atmosphere_pass(
    atmosphere_id: str | None,
    *,
    density_scale: float = 1.0,
    speed_scale: float = 1.0,
    opacity_scale: float = 1.0,
    wind_scale: float = 1.0,
) -> dict[str, Any] | None:
    aid = normalize_atmosphere_id(atmosphere_id)
    if not aid:
        return None
    draw = dict(_ATMOSPHERE_DRAW.get(aid, {"kind": "volume", "density": 0.3, "tint": "#a8b4c8"}))
    try:
        draw["density"] = max(0.0, min(2.5, float(draw.get("density") or 0.3) * float(density_scale)))
    except (TypeError, ValueError):
        pass
    try:
        draw["speed"] = max(0.05, min(4.0, float(draw.get("speed") or 1.0) * float(speed_scale)))
    except (TypeError, ValueError):
        pass
    try:
        base_op = float(draw.get("opacity") or 1.0)
        draw["opacity"] = max(0.0, min(1.0, base_op * float(opacity_scale)))
    except (TypeError, ValueError):
        draw["opacity"] = max(0.0, min(1.0, float(opacity_scale)))
    try:
        draw["wind"] = max(0.0, min(3.0, float(draw.get("wind") or 1.0) * float(wind_scale)))
    except (TypeError, ValueError):
        draw["wind"] = max(0.0, min(3.0, float(wind_scale)))
    # Density 0 = atmosphere off (no wash / no weather).
    enabled = float(draw.get("density") or 0.0) > 0.001 and float(draw.get("opacity") or 0.0) > 0.001
    return {
        "enabled": enabled,
        "atmosphereId": aid,
        "draw": draw,
        "layer": "atmosphere",
    }


def default_atmosphere_id() -> str:
    return NONE
