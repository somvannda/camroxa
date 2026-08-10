"""Shared animation drivers (Layer 4) — evaluate behavior for any target."""

from __future__ import annotations

import math
from typing import Any

from visualizer_studio.presets.animations import (
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
    speed: float = 1.0,
    scale_amount: float = 1.0,
    opacity_amount: float = 1.0,
    rotate_amount: float = 1.0,
    audio_amount: float = 1.0,
) -> dict[str, Any]:
    """Return motion state for a shared behavior id.

    ``speed`` multiplies the timebase (pulse/breathing/rotate rate).
    ``*_amount`` knobs scale each driver channel (1.0 = preset default).
    """
    key = normalize_animation_behavior_id(behavior_id)
    if key is None or key not in _DRIVER_PROFILES:
        return {"scale": 1.0, "opacity": 1.0, "rotation": 0.0, "audio_gain": 0.0, "behavior_id": None}
    _ = target
    try:
        speed_m = max(0.05, min(4.0, float(speed)))
    except (TypeError, ValueError):
        speed_m = 1.0
    scale_m = _clamp_amt(scale_amount)
    opacity_m = _clamp_amt(opacity_amount)
    rotate_m = _clamp_amt(rotate_amount)
    audio_m = _clamp_amt(audio_amount)
    profile = _DRIVER_PROFILES[key]
    level = max(0.0, min(1.0, float(audio_level)))
    t = float(time_sec) * speed_m
    phase = t * (1.2 + abs(profile["rot_speed"]) * rotate_m)
    wave = 0.5 + 0.5 * math.sin(phase * math.tau)
    audio_term = level * profile["audio_gain"] * audio_m
    scale = 1.0 + profile["scale_amp"] * scale_m * (0.35 * wave + 0.65 * audio_term)
    opacity = max(
        0.05,
        min(1.0, 1.0 - profile["opacity_amp"] * opacity_m * (1.0 - wave) * (0.4 + 0.6 * audio_term)),
    )
    rotation = (t * profile["rot_speed"] * rotate_m * 360.0) % 360.0
    return {
        "scale": float(scale),
        "opacity": float(opacity),
        "rotation": float(rotation),
        "audio_gain": float(profile["audio_gain"] * audio_m),
        "behavior_id": key,
        "speed": float(speed_m),
        "scale_amount": float(scale_m),
        "opacity_amount": float(opacity_m),
        "rotate_amount": float(rotate_m),
        "audio_amount": float(audio_m),
    }


def _clamp_amt(value: float, *, lo: float = 0.0, hi: float = 2.5, default: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return float(default)


# Per-behavior audio dials — avoid gain-only collapses (expand≈twist, ripple≈wave).
_SPECTRUM_AUDIO_DIALS: dict[str, dict[str, float]] = {
    "pulse": {"barHeight": 1.25, "kickImpact": 0.55, "motionSmoothing": 0.62, "bassEmphasis": 1.15},
    "bounce": {"barHeight": 1.45, "kickImpact": 0.9, "motionSmoothing": 0.4, "bassEmphasis": 1.35},
    "rotate": {"barHeight": 1.05, "kickImpact": 0.2, "motionSmoothing": 0.78, "bassEmphasis": 1.0},
    "expand": {"barHeight": 1.55, "kickImpact": 0.35, "motionSmoothing": 0.7, "bassEmphasis": 1.05},
    "contract": {"barHeight": 0.85, "kickImpact": 0.4, "motionSmoothing": 0.72, "bassEmphasis": 1.2},
    "ripple": {"barHeight": 1.2, "kickImpact": 0.5, "motionSmoothing": 0.55, "bassEmphasis": 1.1},
    "wave": {"barHeight": 1.35, "kickImpact": 0.45, "motionSmoothing": 0.48, "bassEmphasis": 0.95},
    "twist": {"barHeight": 1.15, "kickImpact": 0.55, "motionSmoothing": 0.5, "bassEmphasis": 1.25},
    "elastic": {"barHeight": 1.6, "kickImpact": 1.0, "motionSmoothing": 0.3, "bassEmphasis": 1.4},
    "fade": {"barHeight": 0.95, "kickImpact": 0.15, "motionSmoothing": 0.85, "bassEmphasis": 0.9},
    "flash": {"barHeight": 1.5, "kickImpact": 1.0, "motionSmoothing": 0.25, "bassEmphasis": 1.3},
    "breathing": {"barHeight": 1.1, "kickImpact": 0.25, "motionSmoothing": 0.8, "bassEmphasis": 1.05},
}


def spectrum_audio_from_behavior(behavior_id: str | None) -> dict[str, float]:
    """Compile-time audio dial hints — unique per behavior id."""
    key = normalize_animation_behavior_id(behavior_id)
    if key and key in _SPECTRUM_AUDIO_DIALS:
        return dict(_SPECTRUM_AUDIO_DIALS[key])
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
