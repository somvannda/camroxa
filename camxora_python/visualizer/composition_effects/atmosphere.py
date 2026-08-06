"""Atmosphere descriptors — weather/fog/sky (Session B ≠ particle emitters)."""

from __future__ import annotations

from typing import Any

from visualizer.presets.atmosphere import normalize_atmosphere_id
from visualizer.scene import NONE

_ATMOSPHERE_DRAW: dict[str, dict[str, Any]] = {
    "fog": {"kind": "volume", "density": 0.45, "tint": "#a8b4c8"},
    "mist": {"kind": "volume", "density": 0.25, "tint": "#c8d0dc"},
    "rain": {"kind": "weather", "density": 0.6, "speed": 1.4},
    "snow": {"kind": "weather", "density": 0.4, "speed": 0.35},
    "storm": {"kind": "weather", "density": 0.85, "speed": 1.8, "flash": 0.3},
    "stars": {"kind": "sky", "density": 0.5, "twinkle": 0.6},
    "clouds": {"kind": "sky", "density": 0.4, "speed": 0.15},
    "dust": {"kind": "volume", "density": 0.3, "tint": "#c4a574"},
    "smoke": {"kind": "volume", "density": 0.5, "tint": "#6b7280"},
    "nebula": {"kind": "sky", "density": 0.55, "tint": "#7c3aed"},
    "aurora": {"kind": "sky", "density": 0.5, "tint": "#22d3ee"},
    "haze": {"kind": "volume", "density": 0.2, "tint": "#e8dcc8"},
    "heatwave": {"kind": "distort", "density": 0.35, "amplitude": 0.02},
    "underwater": {"kind": "volume", "density": 0.4, "tint": "#0e7490", "caustics": 0.5},
    "void": {"kind": "sky", "density": 0.9, "tint": "#020617"},
}


def build_atmosphere_pass(atmosphere_id: str | None) -> dict[str, Any] | None:
    aid = normalize_atmosphere_id(atmosphere_id)
    if not aid:
        return None
    draw = dict(_ATMOSPHERE_DRAW.get(aid, {"kind": "volume", "density": 0.3}))
    return {
        "enabled": True,
        "atmosphereId": aid,
        "draw": draw,
        "layer": "atmosphere",
    }


def default_atmosphere_id() -> str:
    return NONE
