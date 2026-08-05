"""UI/draft helpers for composition-only scene editing (engine v1)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer.presets.animations import list_animation_behavior_options, normalize_animation_behavior_id
from visualizer.presets.materials import list_spectrum_material_options, normalize_spectrum_material_id
from visualizer.presets.palettes import list_color_palette_options, normalize_color_palette_id
from visualizer.presets.particles import list_particle_type_options, normalize_particle_type_id
from visualizer.presets.shapes import list_spectrum_shape_options, normalize_spectrum_shape_id
from visualizer.scene import NONE, default_document, normalize_composition


COMPOSITION_DRAFT_KEYS: tuple[str, ...] = (
    "compositionSpectrumShape",
    "compositionSpectrumMaterial",
    "compositionSpectrumAnimation",
    "compositionParticleType",
    "compositionParticleBehavior",
    "compositionColorPalette",
    "compositionLogoAnimation",
    "compositionOverlayAnimation",
)


def composition_axis_options() -> dict[str, tuple[tuple[str, str], ...]]:
    return {
        "shapes": list_spectrum_shape_options(),
        "materials": list_spectrum_material_options(),
        "animations": list_animation_behavior_options(),
        "particle_types": list_particle_type_options(),
        "palettes": list_color_palette_options(),
    }


def draft_from_composition(composition: dict[str, Any] | None) -> dict[str, Any]:
    scene = normalize_composition(composition)
    return {
        "compositionSpectrumShape": scene["spectrum"]["shape"],
        "compositionSpectrumMaterial": scene["spectrum"]["material"],
        "compositionSpectrumAnimation": scene["spectrum"]["animation"],
        "compositionParticleType": scene["particles"]["type"],
        "compositionParticleBehavior": scene["particles"]["behavior"],
        "compositionColorPalette": scene.get("colorPalette") or NONE,
        "compositionLogoAnimation": scene["logo"]["animation"],
        "compositionOverlayAnimation": scene["overlay"].get("animation") or NONE,
    }


def apply_draft_axes_to_composition(
    composition: dict[str, Any] | None,
    draft: dict[str, Any],
) -> dict[str, Any]:
    scene = normalize_composition(composition)
    shape = normalize_spectrum_shape_id(draft.get("compositionSpectrumShape"))
    material = normalize_spectrum_material_id(draft.get("compositionSpectrumMaterial"))
    animation = normalize_animation_behavior_id(draft.get("compositionSpectrumAnimation"))
    ptype = normalize_particle_type_id(draft.get("compositionParticleType"))
    pbehavior = normalize_animation_behavior_id(draft.get("compositionParticleBehavior"))
    palette = normalize_color_palette_id(draft.get("compositionColorPalette"))
    logo_anim = normalize_animation_behavior_id(draft.get("compositionLogoAnimation"))
    overlay_anim = normalize_animation_behavior_id(draft.get("compositionOverlayAnimation"))

    if shape:
        scene["spectrum"]["shape"] = shape
    elif draft.get("compositionSpectrumShape") in (None, "", NONE):
        scene["spectrum"]["shape"] = NONE
    if material:
        scene["spectrum"]["material"] = material
    elif draft.get("compositionSpectrumMaterial") in (None, "", NONE):
        scene["spectrum"]["material"] = NONE
    if animation:
        scene["spectrum"]["animation"] = animation
    elif draft.get("compositionSpectrumAnimation") in (None, "", NONE):
        scene["spectrum"]["animation"] = NONE
    if ptype:
        scene["particles"]["type"] = ptype
    elif draft.get("compositionParticleType") in (None, "", NONE):
        scene["particles"]["type"] = NONE
    if pbehavior:
        scene["particles"]["behavior"] = pbehavior
    elif draft.get("compositionParticleBehavior") in (None, "", NONE):
        scene["particles"]["behavior"] = NONE
    scene["colorPalette"] = palette
    if logo_anim:
        scene["logo"]["animation"] = logo_anim
    elif draft.get("compositionLogoAnimation") in (None, "", NONE):
        scene["logo"]["animation"] = NONE
    if overlay_anim:
        scene["overlay"]["animation"] = overlay_anim
    elif draft.get("compositionOverlayAnimation") in (None, "", NONE):
        scene["overlay"]["animation"] = NONE
    return scene


def build_composition_save_document(
    *,
    composition: dict[str, Any] | None = None,
    assets: dict[str, Any] | None = None,
    draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = default_document()
    scene = normalize_composition(composition)
    if draft:
        scene = apply_draft_axes_to_composition(scene, draft)
    doc["composition"] = scene
    if isinstance(assets, dict):
        doc["assets"] = {
            "backgroundImage": assets.get("backgroundImage") or assets.get("previewBackground"),
            "logo": assets.get("logo") or assets.get("logoPath"),
            "audio": assets.get("audio") or assets.get("selectedMp3Path"),
        }
    return doc


def new_blank_composition_template(*, name: str = "New Composition") -> dict[str, Any]:
    doc = default_document()
    doc["templateName"] = name
    # Sensible studio default: Neon Circle Pulse + Dust / none behavior.
    doc["composition"]["spectrum"] = {
        "shape": "circle",
        "material": "neon",
        "animation": "pulse",
    }
    doc["composition"]["colorPalette"] = "cyberpunk"
    doc["composition"]["particles"] = {"type": "dust", "behavior": "none"}
    return doc
