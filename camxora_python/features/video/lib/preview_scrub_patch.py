"""Allowlisted live-preview scrub patches (REQ-P2).

High-churn inspector fields update the already-normalized preview template in
place so scrubbing does not call ``normalize_renderer_template`` /
``to_renderer_dict`` every tick. Unknown keys fall back to a full template push.
"""

from __future__ import annotations

from typing import Any

# Draft keys (particles inspector → TemplateNormalizer / particlesSettings).
PREVIEW_SCRUB_PARTICLE_DRAFT_KEYS: frozenset[str] = frozenset(
    {
        "particlesOpacity",
        "particlesSize",
    }
)

# Spectrum layer keys (layer editor → layers[i]).
PREVIEW_SCRUB_LAYER_KEYS: frozenset[str] = frozenset(
    {
        "glow",
        "opacity",
        "barWidth",
    }
)

# Geometry / style keys that must clear spectrum peak cache on full push.
SPECTRUM_PEAK_CACHE_INVALIDATING_KEYS: frozenset[str] = frozenset(
    {
        "style",
        "curved",
        "mirrored",
        "gravity",
        "barCount",
        "pointCount",
        "fillCircle",
        "solidBand",
        "pathMode",
        "frequencyScroll",
        "linearSpan",
    }
)


def draft_patch_is_scrub_allowlisted(patch: dict[str, Any]) -> bool:
    keys = set(patch.keys()) if isinstance(patch, dict) else set()
    return bool(keys) and keys <= PREVIEW_SCRUB_PARTICLE_DRAFT_KEYS


def layer_patch_is_scrub_allowlisted(patch: dict[str, Any]) -> bool:
    keys = set(patch.keys()) if isinstance(patch, dict) else set()
    return bool(keys) and keys <= PREVIEW_SCRUB_LAYER_KEYS


def clamp_layer_scrub_value(key: str, value: Any) -> Any:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    if key == "glow":
        return float(max(0.0, min(100.0, num)))
    if key == "opacity":
        return float(max(0.0, min(1.0, num)))
    if key == "barWidth":
        return float(max(0.5, min(240.0, num)))
    return num


def clamp_particle_scrub_value(draft_key: str, value: Any) -> Any:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    if draft_key == "particlesOpacity":
        return float(max(0.0, min(1.0, num)))
    if draft_key == "particlesSize":
        return float(max(1.0, min(20.0, num)))
    return num


def particle_draft_to_settings_patch(patch: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    if "particlesOpacity" in patch:
        out["opacity"] = float(clamp_particle_scrub_value("particlesOpacity", patch["particlesOpacity"]))
    if "particlesSize" in patch:
        out["size"] = float(clamp_particle_scrub_value("particlesSize", patch["particlesSize"]))
    return out


def layer_scrub_values(patch: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in PREVIEW_SCRUB_LAYER_KEYS:
        if key not in patch:
            continue
        out[key] = float(clamp_layer_scrub_value(key, patch[key]))
    return out
