"""Composition Engine P5 — shared animation behaviors (Layer 4, all 12).

Behaviors are motion recipes attachable to Spectrum, Logo, Overlay, and
Particles. Spectrum uses ``composition.spectrum.animation``; particles reuse
the same ids on ``composition.particles.behavior``. Applying a behavior does
not change spectrum shape or material.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Sequence

from features.video.lib.composition_axes import (
    apply_particles_axes,
    apply_spectrum_axes,
)
from features.video.lib.composition_scene_contract import (
    NONE,
    ensure_composition_on_template,
    normalize_composition_scene,
)

# Canonical Layer 4 list (exactly 12 — no fill slots).
_BEHAVIOR_ROWS: tuple[tuple[str, str], ...] = (
    ("pulse", "Pulse"),
    ("bounce", "Bounce"),
    ("rotate", "Rotate"),
    ("expand", "Expand"),
    ("contract", "Contract"),
    ("ripple", "Ripple"),
    ("wave", "Wave"),
    ("twist", "Twist"),
    ("elastic", "Elastic"),
    ("fade", "Fade"),
    ("flash", "Flash"),
    ("breathing", "Breathing"),
)

ANIMATION_BEHAVIOR_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _BEHAVIOR_ROWS
)
ANIMATION_BEHAVIOR_IDS: frozenset[str] = frozenset(item["id"] for item in ANIMATION_BEHAVIOR_CATALOG)
ANIMATION_BEHAVIOR_COUNT = len(ANIMATION_BEHAVIOR_CATALOG)
assert ANIMATION_BEHAVIOR_COUNT == 12, ANIMATION_BEHAVIOR_COUNT

ANIMATION_TARGETS: tuple[str, ...] = ("spectrum", "logo", "overlay", "particles")

# Spectrum → audioSettings dials (motion intensity, not geometry/look).
_SPECTRUM_AUDIO_RECIPES: dict[str, dict[str, float]] = {
    "pulse": {"barHeight": 1.25, "kickImpact": 0.55, "bassEmphasis": 1.15, "motionSmoothing": 0.65},
    "bounce": {"barHeight": 1.2, "kickImpact": 0.85, "transientFocus": 1.35, "motionSmoothing": 0.45},
    "rotate": {"flyingGlowWingMotionSpeed": 1.4, "motionSmoothing": 0.7},
    "expand": {"barHeight": 1.55, "bassEmphasis": 1.3, "motionSmoothing": 0.6},
    "contract": {"barHeight": 0.65, "bassEmphasis": 0.75, "motionSmoothing": 0.75},
    "ripple": {"trebleShimmer": 1.4, "transientFocus": 1.2, "motionSmoothing": 0.55},
    "wave": {"barHeight": 1.15, "trebleShimmer": 1.2, "motionSmoothing": 0.5},
    "twist": {"flyingGlowWingMotionSpeed": 1.8, "transientFocus": 1.15, "motionSmoothing": 0.55},
    "elastic": {"barHeight": 1.3, "kickImpact": 0.75, "motionSmoothing": 0.35},
    "fade": {"barHeight": 0.9, "peakHoldBlend": 0.4, "motionSmoothing": 0.85},
    "flash": {"kickImpact": 1.0, "peakHoldBlend": 0.7, "transientFocus": 1.4, "motionSmoothing": 0.4},
    "breathing": {"barHeight": 1.1, "bassEmphasis": 1.1, "kickImpact": 0.25, "motionSmoothing": 0.88},
}

# Logo → logoSettings (legacy GPU fields that already exist).
_LOGO_RECIPES: dict[str, dict[str, Any]] = {
    "pulse": {
        "spinEnabled": False,
        "motionMode": "zoom",
        "motionZoomStrength": 1.2,
        "motionVibrateStrength": 0.3,
        "motionSpeed": 1.0,
        "reactivity": 0.7,
    },
    "bounce": {
        "spinEnabled": False,
        "motionMode": "both",
        "motionZoomStrength": 1.4,
        "motionVibrateStrength": 1.2,
        "motionSpeed": 1.3,
        "reactivity": 0.85,
    },
    "rotate": {
        "spinEnabled": True,
        "spinSpeed": 360.0,
        "motionMode": "none",
        "motionZoomStrength": 1.0,
        "motionVibrateStrength": 1.0,
        "motionSpeed": 1.0,
        "reactivity": 0.2,
    },
    "expand": {
        "spinEnabled": False,
        "motionMode": "zoom",
        "motionZoomStrength": 1.6,
        "motionVibrateStrength": 0.2,
        "motionSpeed": 0.9,
        "reactivity": 0.55,
    },
    "contract": {
        "spinEnabled": False,
        "motionMode": "zoom",
        "motionZoomStrength": 0.55,
        "motionVibrateStrength": 0.2,
        "motionSpeed": 0.9,
        "reactivity": 0.45,
    },
    "ripple": {
        "spinEnabled": False,
        "motionMode": "vibrate",
        "motionZoomStrength": 0.8,
        "motionVibrateStrength": 0.9,
        "motionSpeed": 1.1,
        "reactivity": 0.6,
    },
    "wave": {
        "spinEnabled": False,
        "motionMode": "both",
        "motionZoomStrength": 0.9,
        "motionVibrateStrength": 0.8,
        "motionSpeed": 1.0,
        "reactivity": 0.55,
    },
    "twist": {
        "spinEnabled": True,
        "spinSpeed": 180.0,
        "motionMode": "vibrate",
        "motionZoomStrength": 0.7,
        "motionVibrateStrength": 0.6,
        "motionSpeed": 1.2,
        "reactivity": 0.5,
    },
    "elastic": {
        "spinEnabled": False,
        "motionMode": "both",
        "motionZoomStrength": 1.5,
        "motionVibrateStrength": 1.0,
        "motionSpeed": 1.4,
        "reactivity": 0.9,
    },
    "fade": {
        "spinEnabled": False,
        "motionMode": "none",
        "motionZoomStrength": 1.0,
        "motionVibrateStrength": 0.2,
        "motionSpeed": 0.6,
        "reactivity": 0.15,
        "opacity": 0.7,
    },
    "flash": {
        "spinEnabled": False,
        "motionMode": "vibrate",
        "motionZoomStrength": 1.1,
        "motionVibrateStrength": 1.5,
        "motionSpeed": 1.6,
        "reactivity": 1.0,
    },
    "breathing": {
        "spinEnabled": False,
        "motionMode": "zoom",
        "motionZoomStrength": 0.85,
        "motionVibrateStrength": 0.2,
        "motionSpeed": 0.55,
        "reactivity": 0.4,
    },
}

_BEHAVIOR_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in ANIMATION_BEHAVIOR_CATALOG},
    **{item["label"].lower(): item["id"] for item in ANIMATION_BEHAVIOR_CATALOG},
}

SPECTRUM_AUDIO_MOTION_KEYS: frozenset[str] = frozenset(
    {
        "barHeight",
        "kickImpact",
        "bassEmphasis",
        "transientFocus",
        "trebleShimmer",
        "peakHoldBlend",
        "motionSmoothing",
        "flyingGlowWingMotionSpeed",
        # Keep legacy aliases in sync when present.
        "sensitivity",
        "smoothing",
    }
)


def list_animation_behavior_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in ANIMATION_BEHAVIOR_CATALOG)


def normalize_animation_behavior_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in ANIMATION_BEHAVIOR_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _BEHAVIOR_ALIASES:
        return _BEHAVIOR_ALIASES[spaced]
    if raw in _BEHAVIOR_ALIASES:
        return _BEHAVIOR_ALIASES[raw]
    return None


def get_animation_behavior(behavior_id: str | None) -> dict[str, Any] | None:
    key = normalize_animation_behavior_id(behavior_id)
    if not key:
        return None
    item = next(row for row in ANIMATION_BEHAVIOR_CATALOG if row["id"] == key)
    return {
        "id": item["id"],
        "label": item["label"],
        "spectrum_audio": deepcopy(_SPECTRUM_AUDIO_RECIPES[key]),
        "logo": deepcopy(_LOGO_RECIPES[key]),
    }


def _normalize_targets(targets: Sequence[str] | None) -> tuple[str, ...]:
    if targets is None:
        return ANIMATION_TARGETS
    out: list[str] = []
    for raw in targets:
        key = str(raw or "").strip().lower()
        if key in ANIMATION_TARGETS and key not in out:
            out.append(key)
    if not out:
        raise ValueError("targets must include at least one of spectrum/logo/overlay/particles")
    return tuple(out)


def _patch_audio_settings(audio: Any, recipe: dict[str, float]) -> dict[str, Any]:
    out = dict(audio) if isinstance(audio, dict) else {}
    for key, value in recipe.items():
        if key in SPECTRUM_AUDIO_MOTION_KEYS:
            out[key] = float(value)
    if "barHeight" in recipe or "inputGain" in out:
        # Keep sensitivity alias aligned when audio dials are present.
        if "inputGain" in out:
            out["sensitivity"] = float(out["inputGain"])
    if "motionSmoothing" in recipe:
        out["smoothing"] = float(max(0.0, min(0.99, float(recipe["motionSmoothing"]))))
    return out


def _apply_spectrum_motion(template: dict[str, Any], behavior_id: str) -> None:
    recipe = _SPECTRUM_AUDIO_RECIPES[behavior_id]
    audio = template.get("audioSettings")
    if isinstance(audio, dict) or recipe:
        template["audioSettings"] = _patch_audio_settings(audio, recipe)

    instances = template.get("spectrumInstances")
    if isinstance(instances, list):
        next_instances: list[Any] = []
        for inst in instances:
            if not isinstance(inst, dict):
                next_instances.append(inst)
                continue
            cloned = deepcopy(inst)
            cloned["audioSettings"] = _patch_audio_settings(cloned.get("audioSettings"), recipe)
            next_instances.append(cloned)
        template["spectrumInstances"] = next_instances


def _apply_logo_motion(template: dict[str, Any], behavior_id: str) -> None:
    recipe = _LOGO_RECIPES[behavior_id]
    logo = template.get("logoSettings")
    if not isinstance(logo, dict):
        logo = {}
        template["logoSettings"] = logo
    for key, value in recipe.items():
        logo[key] = deepcopy(value) if isinstance(value, (dict, list)) else value
    logo["enabled"] = bool(logo.get("enabled", True))


def _apply_overlay_motion(template: dict[str, Any], behavior_id: str) -> None:
    overlay = template.get("overlaySettings")
    if not isinstance(overlay, dict):
        overlay = {}
        template["overlaySettings"] = overlay
    overlay["animation"] = behavior_id


def _apply_particles_motion(template: dict[str, Any], behavior_id: str) -> None:
    particles = template.get("particlesSettings")
    if not isinstance(particles, dict):
        particles = {}
        template["particlesSettings"] = particles
    particles["behavior"] = behavior_id


def apply_spectrum_animation_to_template(template: dict[str, Any], behavior_id: str) -> dict[str, Any]:
    """Apply Layer 4 behavior onto spectrum only — preserves shape / material."""
    return apply_animation_behavior_to_template(template, behavior_id, targets=("spectrum",))


def apply_animation_behavior_to_template(
    template: dict[str, Any],
    behavior_id: str,
    *,
    targets: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Attach one behavior id to one or more scene objects.

    Spectrum → ``composition.spectrum.animation`` (+ audio dial recipes)
    Logo → ``composition.logo.animation`` (+ logoSettings motion)
    Overlay → ``composition.overlay.animation`` (+ overlaySettings.animation)
    Particles → ``composition.particles.behavior`` (+ particlesSettings.behavior)
    """
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    key = normalize_animation_behavior_id(behavior_id)
    if key is None:
        raise ValueError(f"unknown animation behavior: {behavior_id!r}")
    chosen = _normalize_targets(targets)

    ensure_composition_on_template(template)
    scene = normalize_composition_scene(template.get("composition"))
    prev_shape = scene["spectrum"]["shape"]
    prev_material = scene["spectrum"]["material"]
    prev_palette = scene.get("colorPalette")
    prev_particle_type = scene["particles"]["type"]

    if "spectrum" in chosen:
        _apply_spectrum_motion(template, key)
        scene = apply_spectrum_axes(
            scene,
            shape=prev_shape if prev_shape else NONE,
            material=prev_material if prev_material else NONE,
            animation=key,
        )
        if not prev_shape or prev_shape == NONE:
            scene["spectrum"]["shape"] = NONE
        if not prev_material or prev_material == NONE:
            scene["spectrum"]["material"] = NONE

    if "logo" in chosen:
        _apply_logo_motion(template, key)
        scene["logo"]["animation"] = key

    if "overlay" in chosen:
        _apply_overlay_motion(template, key)
        scene["overlay"]["animation"] = key

    if "particles" in chosen:
        _apply_particles_motion(template, key)
        scene = apply_particles_axes(
            scene,
            type=prev_particle_type if prev_particle_type else NONE,
            behavior=key,
        )
        if not prev_particle_type or prev_particle_type == NONE:
            scene["particles"]["type"] = NONE

    if prev_palette:
        scene["colorPalette"] = prev_palette
    template["composition"] = normalize_composition_scene(scene)
    return template


def animation_behavior_supported_on(target: str) -> bool:
    return str(target or "").strip().lower() in ANIMATION_TARGETS


def iter_animation_behavior_ids() -> Iterable[str]:
    return (item["id"] for item in ANIMATION_BEHAVIOR_CATALOG)
