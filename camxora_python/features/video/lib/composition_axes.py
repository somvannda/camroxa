"""Composition Engine P1 — orthogonal axes (independent apply).

Axis setters touch only the named field. Convenience preset helpers may fill
several axes at once (UI preset buttons) but must not be the only way to edit.

GPU still reads legacy fields; these APIs mutate ``composition`` (and optionally
sync ``style`` / particle variant aliases).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from features.video.lib.composition_scene_contract import (
    NONE,
    ensure_composition_on_template,
    normalize_composition_scene,
)

__all__ = (
    "apply_background_axes",
    "apply_lighting_axes",
    "apply_particles_axes",
    "apply_spectrum_axes",
    "apply_spectrum_preset_convenience",
    "apply_particles_preset_convenience",
    "apply_lighting_preset_convenience",
    "sync_composition_axes_on_template",
    "sync_legacy_aliases_from_composition",
)


def apply_spectrum_axes(
    composition: dict[str, Any] | None,
    *,
    shape: str | None = None,
    material: str | None = None,
    animation: str | None = None,
) -> dict[str, Any]:
    """Set spectrum axes independently. Omitted kwargs are left unchanged."""
    scene = normalize_composition_scene(composition)
    if shape is not None:
        scene["spectrum"]["shape"] = _axis_id(shape, NONE)
    if material is not None:
        scene["spectrum"]["material"] = _axis_id(material, NONE)
    if animation is not None:
        scene["spectrum"]["animation"] = _axis_id(animation, NONE)
    return scene


def apply_particles_axes(
    composition: dict[str, Any] | None,
    *,
    type: str | None = None,  # noqa: A002 — architecture-tree field name
    behavior: str | None = None,
) -> dict[str, Any]:
    scene = normalize_composition_scene(composition)
    if type is not None:
        scene["particles"]["type"] = _axis_id(type, NONE)
    if behavior is not None:
        scene["particles"]["behavior"] = _axis_id(behavior, NONE)
    return scene


def apply_lighting_axes(
    composition: dict[str, Any] | None,
    *,
    effect: str | None = None,
    trigger: str | None = None,
) -> dict[str, Any]:
    scene = normalize_composition_scene(composition)
    if effect is not None:
        scene["lighting"]["effect"] = _axis_id(effect, NONE)
    if trigger is not None:
        scene["lighting"]["trigger"] = _axis_id(trigger, NONE)
    return scene


def apply_background_axes(
    composition: dict[str, Any] | None,
    *,
    image: str | None = None,
    motion: str | None = None,
    atmosphere: str | None = None,
    clear_image: bool = False,
) -> dict[str, Any]:
    scene = normalize_composition_scene(composition)
    if clear_image:
        scene["background"]["image"] = None
    elif image is not None:
        text = str(image).strip()
        scene["background"]["image"] = text or None
    if motion is not None:
        scene["background"]["motion"] = _axis_id(motion, "static")
    if atmosphere is not None:
        scene["background"]["atmosphere"] = _axis_id(atmosphere, NONE)
    return scene


def apply_spectrum_preset_convenience(
    composition: dict[str, Any] | None,
    preset_key: str,
) -> dict[str, Any]:
    """UI preset button helper: sets ``shape`` from legacy style id.

    Does **not** clear an existing material or animation (orthogonal).
    """
    from features.video.lib.spectrum_style_registry import normalize_spectrum_preset_key_for_apply

    shape = normalize_spectrum_preset_key_for_apply(preset_key)
    return apply_spectrum_axes(composition, shape=shape)


def apply_particles_preset_convenience(
    composition: dict[str, Any] | None,
    preset_key: str,
) -> dict[str, Any]:
    """UI particle preset: sets ``type`` only; preserves ``behavior``."""
    key = _axis_id(preset_key, NONE)
    return apply_particles_axes(composition, type=key)


def apply_lighting_preset_convenience(
    composition: dict[str, Any] | None,
    *,
    effect: str | None = None,
    trigger: str | None = None,
) -> dict[str, Any]:
    """UI lighting preset: apply only provided lighting axes."""
    return apply_lighting_axes(composition, effect=effect, trigger=trigger)


def sync_composition_axes_on_template(template: dict[str, Any]) -> dict[str, Any]:
    """Ensure ``composition`` exists and reflects legacy aliases without wiping axes."""
    return ensure_composition_on_template(template)


def sync_legacy_aliases_from_composition(template: dict[str, Any]) -> dict[str, Any]:
    """Write composition spectrum.shape → legacy ``style`` when shape is set.

    Material/animation have no legacy GPU fields yet (P4/P5).
    Does **not** re-project from legacy first (that would clobber authoring axes).
    """
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    scene = normalize_composition_scene(template.get("composition"))
    template["composition"] = scene
    shape = str(scene.get("spectrum", {}).get("shape") or "").strip()
    if shape and shape != NONE:
        template["style"] = shape
    particle_type = str(scene.get("particles", {}).get("type") or "").strip()
    if particle_type and particle_type != NONE:
        particles = template.get("particlesSettings")
        if not isinstance(particles, dict):
            particles = {}
            template["particlesSettings"] = particles
        particles["variant"] = particle_type
    return template


def attach_spectrum_preset_to_composition(template: dict[str, Any], preset_key: str) -> dict[str, Any]:
    """After a legacy spectrum preset apply, update composition.shape only."""
    ensure_composition_on_template(template)
    template["composition"] = apply_spectrum_preset_convenience(template.get("composition"), preset_key)
    return template


def _axis_id(value: Any, default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text else default
