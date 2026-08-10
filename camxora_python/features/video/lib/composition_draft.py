"""UI/draft helpers for composition-only scene editing (engine v1 / studio P0–P11)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer_video.composition_effects.audio_mapping import normalize_audio_mapping
from visualizer_video.presets.animations import list_animation_behavior_options, normalize_animation_behavior_id
from visualizer_video.presets.atmosphere import list_atmosphere_options, normalize_atmosphere_id
from visualizer_video.presets.audio_buses import (
    list_audio_bus_options,
    list_audio_mapping_target_options,
    normalize_audio_bus_id,
)
from visualizer_video.presets.background_motion import (
    list_background_motion_options,
    normalize_background_motion_id,
)
from visualizer_video.presets.camera import list_camera_behavior_options, normalize_camera_behavior_id
from visualizer_video.presets.lighting import (
    list_lighting_effect_options,
    list_lighting_trigger_options,
    normalize_lighting_effect_id,
    normalize_lighting_trigger_id,
)
from visualizer_video.presets.materials import list_spectrum_material_options, normalize_spectrum_material_id
from visualizer_video.presets.palettes import list_color_palette_options, normalize_color_palette_id
from visualizer_video.presets.particles import list_particle_type_options, normalize_particle_type_id
from visualizer_video.presets.post import list_post_effect_options, normalize_post_effects_list
from visualizer_video.presets.shapes import list_spectrum_shape_options, normalize_spectrum_shape_id
from visualizer_video.scene import NONE, default_document, normalize_composition


COMPOSITION_DRAFT_KEYS: tuple[str, ...] = (
    "compositionSpectrumShape",
    "compositionSpectrumMaterial",
    "compositionSpectrumAnimation",
    "compositionParticleType",
    "compositionParticleBehavior",
    "compositionColorPalette",
    "compositionLogoAnimation",
    "compositionOverlayAnimation",
    "compositionOverlayEnabled",
    "compositionTextEnabled",
    "compositionBackgroundMotion",
    "compositionBackgroundAtmosphere",
    "compositionLightingEffect",
    "compositionLightingTrigger",
    "compositionCameraBehavior",
    "compositionPostEffects",
    "compositionAudioMapping",
)


def composition_axis_options() -> dict[str, tuple[tuple[str, str], ...]]:
    return {
        "shapes": list_spectrum_shape_options(),
        "materials": list_spectrum_material_options(),
        "animations": list_animation_behavior_options(),
        "particle_types": list_particle_type_options(),
        "palettes": list_color_palette_options(),
        "lighting_effects": list_lighting_effect_options(),
        "lighting_triggers": list_lighting_trigger_options(),
        "camera_behaviors": list_camera_behavior_options(),
        "atmosphere": list_atmosphere_options(),
        "background_motions": list_background_motion_options(),
        "post_effects": list_post_effect_options(),
        "audio_buses": list_audio_bus_options(),
        "audio_targets": list_audio_mapping_target_options(),
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
        "compositionOverlayEnabled": bool(scene["overlay"].get("enabled", False)),
        "compositionTextEnabled": bool(scene["text"].get("enabled", False)),
        "compositionBackgroundMotion": scene["background"].get("motion") or "static",
        "compositionBackgroundAtmosphere": scene["background"].get("atmosphere") or NONE,
        "compositionLightingEffect": scene["lighting"].get("effect") or NONE,
        "compositionLightingTrigger": scene["lighting"].get("trigger") or NONE,
        "compositionCameraBehavior": scene["camera"].get("behavior") or NONE,
        "compositionPostEffects": list(scene["postProcessing"].get("effects") or []),
        "compositionAudioMapping": dict(scene["audio"].get("mapping") or {}),
    }


def _set_or_none(scene_dict: dict[str, Any], key: str, normalized: str | None, raw: Any) -> None:
    if normalized:
        scene_dict[key] = normalized
    elif raw in (None, "", NONE):
        scene_dict[key] = NONE


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

    _set_or_none(scene["spectrum"], "shape", shape, draft.get("compositionSpectrumShape"))
    _set_or_none(scene["spectrum"], "material", material, draft.get("compositionSpectrumMaterial"))
    _set_or_none(scene["spectrum"], "animation", animation, draft.get("compositionSpectrumAnimation"))
    _set_or_none(scene["particles"], "type", ptype, draft.get("compositionParticleType"))
    _set_or_none(scene["particles"], "behavior", pbehavior, draft.get("compositionParticleBehavior"))
    scene["colorPalette"] = palette
    _set_or_none(scene["logo"], "animation", logo_anim, draft.get("compositionLogoAnimation"))
    _set_or_none(scene["overlay"], "animation", overlay_anim, draft.get("compositionOverlayAnimation"))

    if "compositionOverlayEnabled" in draft:
        scene["overlay"]["enabled"] = bool(draft.get("compositionOverlayEnabled"))
    if "compositionTextEnabled" in draft:
        scene["text"]["enabled"] = bool(draft.get("compositionTextEnabled"))

    motion = normalize_background_motion_id(draft.get("compositionBackgroundMotion"))
    if motion:
        scene["background"]["motion"] = motion
    elif draft.get("compositionBackgroundMotion") in (None, "", NONE):
        scene["background"]["motion"] = "static"

    atm = normalize_atmosphere_id(draft.get("compositionBackgroundAtmosphere"))
    _set_or_none(scene["background"], "atmosphere", atm, draft.get("compositionBackgroundAtmosphere"))

    le = normalize_lighting_effect_id(draft.get("compositionLightingEffect"))
    _set_or_none(scene["lighting"], "effect", le, draft.get("compositionLightingEffect"))
    lt = normalize_lighting_trigger_id(draft.get("compositionLightingTrigger"))
    _set_or_none(scene["lighting"], "trigger", lt, draft.get("compositionLightingTrigger"))

    cam = normalize_camera_behavior_id(draft.get("compositionCameraBehavior"))
    _set_or_none(scene["camera"], "behavior", cam, draft.get("compositionCameraBehavior"))

    if "compositionPostEffects" in draft:
        scene["postProcessing"]["effects"] = normalize_post_effects_list(
            draft.get("compositionPostEffects")
        )

    if "compositionAudioMapping" in draft:
        scene["audio"]["mapping"] = normalize_audio_mapping(draft.get("compositionAudioMapping"))

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
    return doc


def merge_composition_into_template(template: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(template) if isinstance(template, dict) else {}
    existing = out.get("composition") if isinstance(out.get("composition"), dict) else {}
    out["schema"] = "camxora.composition"
    out["composition"] = apply_draft_axes_to_composition(existing, draft)
    return out
