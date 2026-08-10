"""Lighting draw descriptors (Layer 2 — bolts/aura/beams; not whole-frame post)."""

from __future__ import annotations

from typing import Any

from visualizer_studio.presets.lighting import normalize_lighting_effect_id, normalize_lighting_trigger_id
from visualizer_studio.scene import NONE

# Per-effect draw hints consumed by GPU/preview bridge (compiler output only).
_EFFECT_DRAW: dict[str, dict[str, Any]] = {
    "lightning": {"mode": "bolts", "intensity": 1.0, "branches": 3},
    "aura": {"mode": "radial_glow", "intensity": 0.7, "radius": 0.45},
    "glow": {"mode": "soft_glow", "intensity": 0.55, "radius": 0.35},
    "god_rays": {"mode": "rays", "intensity": 0.8, "count": 8},
    "lens_flare": {"mode": "flare", "intensity": 0.9, "ghosts": 4},
    "light_beam": {"mode": "beam", "intensity": 0.75, "width": 0.12},
    "light_sweep": {"mode": "sweep", "intensity": 0.65, "speed": 1.2},
    "neon_rim": {"mode": "rim", "intensity": 0.85, "thickness": 0.04},
    "halo": {"mode": "ring", "intensity": 0.7, "radius": 0.5},
    "energy_pulse": {"mode": "pulse_ring", "intensity": 0.9, "frequency": 2.0},
    "strobe_flash": {"mode": "flash", "intensity": 1.0, "duty": 0.08},
    "rim_light": {"mode": "edge_light", "intensity": 0.75, "thickness": 0.05},
    "spot_cone": {"mode": "cone", "intensity": 0.8, "angle": 35.0},
    "volumetric_shaft": {"mode": "volume_shaft", "intensity": 0.7, "density": 0.4},
    "color_wash": {"mode": "wash", "intensity": 0.5, "coverage": 1.0},
}


def build_lighting_pass(
    effect_id: str | None,
    trigger_id: str | None,
    *,
    palette_solid: str = "#ffffff",
) -> dict[str, Any] | None:
    eid = normalize_lighting_effect_id(effect_id)
    if not eid:
        return None
    tid = normalize_lighting_trigger_id(trigger_id) or NONE
    draw = dict(_EFFECT_DRAW.get(eid, {"mode": "glow", "intensity": 0.5}))
    return {
        "enabled": True,
        "effectId": eid,
        "triggerId": tid,
        "color": palette_solid,
        "draw": draw,
        # Session B ownership: lighting ≠ atmosphere rain / particle rain / post glow.
        "layer": "lighting",
    }
