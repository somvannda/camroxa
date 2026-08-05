"""Particle emitters — type × behavior (engine-true)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer.animations import evaluate_behavior
from visualizer.presets.particles import (
    PARTICLE_TYPE_COUNT,
    PARTICLE_TYPE_IDS,
    get_particle_type,
    normalize_particle_type_id,
)
from visualizer.scene import NONE


def build_particle_emitter(
    type_id: str | None,
    behavior_id: str | None = None,
    *,
    palette_solid: str | None = None,
) -> dict[str, Any] | None:
    """Build an emitter config from catalog type + shared behavior."""
    particle = get_particle_type(type_id)
    if particle is None:
        return None
    emitter = deepcopy(particle["emitter"])
    emitter["typeId"] = particle["id"]
    emitter["enabled"] = True
    if palette_solid:
        emitter["color"] = palette_solid
        emitter["reactColor"] = "#ffffff"

    bid = str(behavior_id or "").strip()
    if bid and bid != NONE:
        motion = evaluate_behavior(bid, time_sec=0.0, audio_level=0.5, target="particles")
        emitter["behaviorId"] = bid
        emitter["speed"] = float(emitter.get("speed", 1.0)) * float(motion["scale"])
        emitter["opacity"] = float(emitter.get("opacity", 1.0)) * float(motion["opacity"])
        emitter["reactStrength"] = 0.35 + 0.65 * float(motion.get("audio_gain") or 0.0)
    else:
        emitter["behaviorId"] = NONE
        emitter["reactStrength"] = 0.45
    return emitter


def emitters_visibly_distinct(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Rain vs Snow (etc.) must differ in travel/speed/size identity."""
    keys = ("travelMode", "speed", "size", "spawnArea", "style")
    return any(a.get(k) != b.get(k) for k in keys)


__all__ = (
    "PARTICLE_TYPE_COUNT",
    "PARTICLE_TYPE_IDS",
    "build_particle_emitter",
    "emitters_visibly_distinct",
    "get_particle_type",
    "normalize_particle_type_id",
)
