"""Whole-frame post stack (Layer 3 — not spectrum materials)."""

from __future__ import annotations

from typing import Any

from visualizer_studio.presets.post import normalize_post_effect_id, normalize_post_effects_list

# Compiler → GPU `effects` key mapping (existing preview understands many of these).
_GPU_EFFECT_KEYS: dict[str, str] = {
    "bloom": "bloom",
    "color_grading": "color_grading",
    "tone_mapping": "tone_mapping",
    "hdr": "hdr",
    "exposure": "exposure",
    "gamma": "gamma",
    "contrast": "contrast",
    "saturation": "saturation",
    "vignette": "vignette",
    "chromatic_aberration": "chromatic_aberration",
    "film_grain": "film_grain",
    "sharpen": "sharpen",
    "motion_blur": "motion_blur",
    "depth_of_field": "depth_of_field",
    "lens_distortion": "lens_distortion",
    "glow": "glow",
    "letterbox": "letterbox",
    "posterize": "posterize",
    "rgb_split": "rgb_split",
    "soft_diffusion": "soft_diffusion",
}

_DEFAULT_PARAMS: dict[str, dict[str, float]] = {
    "bloom": {"amount": 0.45},
    "color_grading": {"amount": 0.35},
    "tone_mapping": {"amount": 0.5},
    "hdr": {"amount": 0.4},
    "exposure": {"amount": 0.0},
    "gamma": {"amount": 1.0},
    "contrast": {"amount": 0.1},
    "saturation": {"amount": 0.1},
    "vignette": {"amount": 0.35},
    "chromatic_aberration": {"amount": 0.25},
    "film_grain": {"amount": 0.2},
    "sharpen": {"amount": 0.2},
    "motion_blur": {"amount": 0.15},
    "depth_of_field": {"amount": 0.25},
    "lens_distortion": {"amount": 0.15},
    "glow": {"amount": 0.4},
    "letterbox": {"amount": 0.12},
    "posterize": {"amount": 0.3},
    "rgb_split": {"amount": 0.2},
    "soft_diffusion": {"amount": 0.25},
}


def build_post_stack(effect_ids: list[str] | None) -> dict[str, Any]:
    ids = normalize_post_effects_list(effect_ids or [])
    stack: list[dict[str, Any]] = []
    gpu_effects: dict[str, Any] = {}
    for eid in ids:
        params = dict(_DEFAULT_PARAMS.get(eid, {"amount": 0.3}))
        stack.append({"id": eid, "enabled": True, "params": params, "layer": "post"})
        gpu_key = _GPU_EFFECT_KEYS.get(eid, eid)
        gpu_effects[gpu_key] = {"enabled": True, **params}
    return {
        "enabled": bool(stack),
        "effects": stack,
        "gpuEffects": gpu_effects,
    }


def toggle_post_effect(current: list[str], effect_id: str, enabled: bool) -> list[str]:
    eid = normalize_post_effect_id(effect_id)
    if not eid:
        return list(current)
    out = [x for x in current if x != eid]
    if enabled:
        out.append(eid)
    return out
