"""Audio buses + mapping — Session C v1 FFT heuristics for Vocals/Melody/Snare."""

from __future__ import annotations

from typing import Any

from visualizer.presets.audio_buses import (
    AUDIO_BUS_IDS,
    HEURISTIC_AUDIO_BUS_IDS,
    normalize_audio_bus_id,
)
from visualizer.scene import NONE

# Mapping target keys on composition.audio.mapping
MAPPING_TARGETS: tuple[str, ...] = ("spectrum", "lighting", "particles", "camera", "logo")


def normalize_audio_mapping(raw: Any) -> dict[str, str]:
    out: dict[str, str] = {key: NONE for key in MAPPING_TARGETS}
    if not isinstance(raw, dict):
        return out
    for target in MAPPING_TARGETS:
        bus = normalize_audio_bus_id(raw.get(target))
        out[target] = bus or NONE
    return out


def resolve_bus_levels(
    *,
    bass: float = 0.0,
    treble: float = 0.0,
    kick: float = 0.0,
    overall: float = 0.0,
    mid: float = 0.0,
    presence: float = 0.0,
    transient_mid: float = 0.0,
) -> dict[str, float]:
    """Map FFT/envelope proxies → named buses.

    Heuristic buses (documented in UI):
    - vocals ≈ presence band (2–5 kHz proxy)
    - melody ≈ mid harmonic energy
    - snare ≈ mid-band transient
    """
    b = _clamp(bass)
    t = _clamp(treble)
    k = _clamp(kick)
    o = _clamp(overall)
    m = _clamp(mid)
    p = _clamp(presence)
    sn = _clamp(transient_mid)

    return {
        "bass": b,
        "treble": t,
        "vocals": p,  # heuristic
        "beat": max(k, b * 0.6),
        "melody": m,  # heuristic
        "kick": k,
        "snare": sn,  # heuristic
        "overall_loudness": o,
    }


def apply_mapping_levels(
    mapping: dict[str, str],
    bus_levels: dict[str, float],
) -> dict[str, float]:
    """Return per-target drive levels from mapping × bus levels."""
    out: dict[str, float] = {}
    for target in MAPPING_TARGETS:
        bus = mapping.get(target) or NONE
        if bus == NONE or bus not in AUDIO_BUS_IDS:
            out[target] = 0.0
        else:
            out[target] = float(bus_levels.get(bus, 0.0))
    return out


def bus_is_heuristic(bus_id: str | None) -> bool:
    return bool(bus_id) and bus_id in HEURISTIC_AUDIO_BUS_IDS


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
