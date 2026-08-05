"""Shared animation drivers (Layer 4) — evaluate behavior for any target."""

from __future__ import annotations

import math
from typing import Any

from visualizer.presets.animations import (
    ANIMATION_BEHAVIOR_COUNT,
    ANIMATION_BEHAVIOR_IDS,
    ANIMATION_TARGETS,
    normalize_animation_behavior_id,
)

# Driver outputs are engine motion state (not legacy logoSettings bags).
_DRIVER_PROFILES: dict[str, dict[str, float]] = {
    "pulse": {"scale_amp": 0.12, "opacity_amp": 0.08, "rot_speed": 0.0, "audio_gain": 0.55},
    "bounce": {"scale_amp": 0.22, "opacity_amp": 0.05, "rot_speed": 0.0, "audio_gain": 0.85},
    "rotate": {"scale_amp": 0.02, "opacity_amp": 0.0, "rot_speed": 1.0, "audio_gain": 0.2},
    "expand": {"scale_amp": 0.28, "opacity_amp": 0.0, "rot_speed": 0.0, "audio_gain": 0.45},
    "contract": {"scale_amp": -0.18, "opacity_amp": 0.0, "rot_speed": 0.0, "audio_gain": 0.4},
    "ripple": {"scale_amp": 0.1, "opacity_amp": 0.12, "rot_speed": 0.15, "audio_gain": 0.5},
    "wave": {"scale_amp": 0.14, "opacity_amp": 0.06, "rot_speed": 0.25, "audio_gain": 0.5},
    "twist": {"scale_amp": 0.08, "opacity_amp": 0.04, "rot_speed": 0.75, "audio_gain": 0.45},
    "elastic": {"scale_amp": 0.3, "opacity_amp": 0.1, "rot_speed": 0.1, "audio_gain": 0.9},
    "fade": {"scale_amp": 0.04, "opacity_amp": 0.35, "rot_speed": 0.0, "audio_gain": 0.15},
    "flash": {"scale_amp": 0.18, "opacity_amp": 0.45, "rot_speed": 0.0, "audio_gain": 1.0},
    "breathing": {"scale_amp": 0.09, "opacity_amp": 0.1, "rot_speed": 0.0, "audio_gain": 0.25},
}


def evaluate_behavior(
    behavior_id: str | None,
    *,
    time_sec: float = 0.0,
    audio_level: float = 0.0,
    target: str = "spectrum",
) -> dict[str, Any]:
    """Return motion state for a shared behavior id."""
    key = normalize_animation_behavior_id(behavior_id)
    if key is None or key not in _DRIVER_PROFILES:
        return {"scale": 1.0, "opacity": 1.0, "rotation": 0.0, "audio_gain": 0.0, "behavior_id": None}
    _ = target
    profile = _DRIVER_PROFILES[key]
    level = max(0.0, min(1.0, float(audio_level)))
    phase = float(time_sec) * (1.2 + abs(profile["rot_speed"]))
    wave = 0.5 + 0.5 * math.sin(phase * math.tau)
    audio_term = level * profile["audio_gain"]
    scale = 1.0 + profile["scale_amp"] * (0.35 * wave + 0.65 * audio_term)
    opacity = max(0.05, min(1.0, 1.0 - profile["opacity_amp"] * (1.0 - wave) * (0.4 + 0.6 * audio_term)))
    rotation = (float(time_sec) * profile["rot_speed"] * 360.0) % 360.0
    return {
        "scale": float(scale),
        "opacity": float(opacity),
        "rotation": float(rotation),
        "audio_gain": float(profile["audio_gain"]),
        "behavior_id": key,
    }


def spectrum_audio_from_behavior(behavior_id: str | None) -> dict[str, float]:
    """Compile-time audio dial hints derived from the shared driver (engine-owned)."""
    state = evaluate_behavior(behavior_id, time_sec=0.0, audio_level=1.0, target="spectrum")
    gain = float(state.get("audio_gain") or 0.0)
    return {
        "barHeight": 1.0 + 0.4 * gain,
        "kickImpact": gain,
        "motionSmoothing": max(0.2, 0.9 - 0.5 * gain),
        "bassEmphasis": 1.0 + 0.2 * gain,
    }


__all__ = (
    "ANIMATION_BEHAVIOR_COUNT",
    "ANIMATION_BEHAVIOR_IDS",
    "ANIMATION_TARGETS",
    "evaluate_behavior",
    "normalize_animation_behavior_id",
    "spectrum_audio_from_behavior",
)
