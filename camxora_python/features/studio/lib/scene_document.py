"""Studio scene document helpers — camxora.composition as v1 authority."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer.composition_effects.audio_mapping import normalize_audio_mapping
from visualizer.presets.animations import (
    list_animation_behavior_options,
    normalize_animation_behavior_id,
)
from visualizer.presets.atmosphere import list_atmosphere_options, normalize_atmosphere_id
from visualizer.presets.audio_buses import (
    list_audio_bus_options,
    list_audio_mapping_target_options,
)
from visualizer.presets.background_motion import (
    list_background_motion_options,
    normalize_background_motion_id,
)
from visualizer.presets.camera import list_camera_behavior_options, normalize_camera_behavior_id
from visualizer.presets.lighting import (
    list_lighting_effect_options,
    list_lighting_trigger_options,
    normalize_lighting_effect_id,
    normalize_lighting_trigger_id,
)
from visualizer.presets.materials import (
    list_spectrum_material_options,
    normalize_spectrum_material_id,
)
from visualizer.presets.palettes import list_color_palette_options, normalize_color_palette_id
from visualizer.presets.particles import list_particle_type_options, normalize_particle_type_id
from visualizer.presets.post import list_post_effect_options, normalize_post_effects_list
from visualizer.presets.shapes import list_spectrum_shape_options, normalize_spectrum_shape_id
from visualizer.scene import NONE, default_document, normalize_assets, normalize_composition


SCENE_TREE_NODES: tuple[tuple[str, str], ...] = (
    ("palette", "Color Palette"),
    ("background", "Background"),
    ("spectrum", "Spectrum"),
    ("logo", "Logo"),
    ("text", "Text"),
    ("overlay", "Overlay"),
    ("particles", "Particles"),
    ("lighting", "Lighting"),
    ("camera", "Camera"),
    ("post", "Post"),
    ("audio_mapping", "Audio Mapping"),
)


def catalog_options() -> dict[str, tuple[tuple[str, str], ...]]:
    return {
        "palettes": list_color_palette_options(),
        "shapes": list_spectrum_shape_options(),
        "materials": list_spectrum_material_options(),
        "animations": list_animation_behavior_options(),
        "particle_types": list_particle_type_options(),
        "lighting_effects": list_lighting_effect_options(),
        "lighting_triggers": list_lighting_trigger_options(),
        "camera_behaviors": list_camera_behavior_options(),
        "atmosphere": list_atmosphere_options(),
        "background_motions": list_background_motion_options(),
        "post_effects": list_post_effect_options(),
        "audio_buses": list_audio_bus_options(),
        "audio_targets": list_audio_mapping_target_options(),
    }


def blank_studio_document(*, name: str = "Untitled Composition") -> dict[str, Any]:
    doc = default_document()
    doc["name"] = name
    doc["templateName"] = name
    return doc


def normalize_studio_document(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return blank_studio_document()
    doc = default_document()
    doc["composition"] = normalize_composition(raw.get("composition"))
    doc["assets"] = normalize_assets(raw.get("assets"))
    name = str(raw.get("name") or raw.get("templateName") or "Untitled Composition").strip()
    doc["name"] = name or "Untitled Composition"
    doc["templateName"] = doc["name"]
    if "id" in raw:
        doc["id"] = str(raw["id"])
    # Studio extras live beside composition (not stripped on every axis patch).
    doc["spectrumAttachToLogo"] = bool(raw.get("spectrumAttachToLogo", False))
    doc["albumEnabled"] = bool(raw.get("albumEnabled", False))
    doc["titleEnabled"] = bool(raw.get("titleEnabled", False))
    doc["albumManualText"] = str(raw.get("albumManualText") or "")
    doc["titleManualText"] = str(raw.get("titleManualText") or "")
    doc["overlayStyle"] = str(raw.get("overlayStyle") or "film_grain")
    doc["studioMode"] = str(raw.get("studioMode") or "creator")
    return doc


def apply_axis_patch(doc: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply inspector axis patches onto a studio document (immutable-style copy)."""
    out = deepcopy(normalize_studio_document(doc))
    comp = out["composition"]
    assets = out["assets"]

    if "compositionColorPalette" in patch:
        palette = normalize_color_palette_id(patch.get("compositionColorPalette"))
        comp["colorPalette"] = palette

    if "compositionBackgroundMotion" in patch:
        motion = normalize_background_motion_id(patch.get("compositionBackgroundMotion"))
        comp["background"]["motion"] = motion or "static"
    if "compositionBackgroundAtmosphere" in patch:
        atm = normalize_atmosphere_id(patch.get("compositionBackgroundAtmosphere"))
        comp["background"]["atmosphere"] = atm or NONE
    if "backgroundEnabled" in patch and not bool(patch.get("backgroundEnabled")):
        # Disable clears the path so bind-state stays consistent.
        assets["backgroundImage"] = None
        comp["background"]["image"] = None

    if "backgroundImage" in patch or "compositionBackgroundImage" in patch:
        path = str(
            patch.get("backgroundImage") or patch.get("compositionBackgroundImage") or ""
        ).strip() or None
        assets["backgroundImage"] = path
        comp["background"]["image"] = path

    if "compositionSpectrumShape" in patch:
        shape = normalize_spectrum_shape_id(patch.get("compositionSpectrumShape"))
        comp["spectrum"]["shape"] = shape or NONE
    if "compositionSpectrumMaterial" in patch:
        material = normalize_spectrum_material_id(patch.get("compositionSpectrumMaterial"))
        comp["spectrum"]["material"] = material or NONE
    if "compositionSpectrumAnimation" in patch:
        anim = normalize_animation_behavior_id(patch.get("compositionSpectrumAnimation"))
        comp["spectrum"]["animation"] = anim or NONE
    if "spectrumEnabled" in patch and not bool(patch.get("spectrumEnabled")):
        comp["spectrum"]["shape"] = NONE

    if "compositionLogoAnimation" in patch:
        anim = normalize_animation_behavior_id(patch.get("compositionLogoAnimation"))
        comp["logo"]["animation"] = anim or NONE
    if "logoEnabled" in patch:
        comp["logo"]["enabled"] = bool(patch.get("logoEnabled"))
    if "logoPath" in patch or "compositionLogoPath" in patch:
        path = str(patch.get("logoPath") or patch.get("compositionLogoPath") or "").strip() or None
        assets["logo"] = path
    if "spectrumAttachToLogo" in patch:
        out["spectrumAttachToLogo"] = bool(patch.get("spectrumAttachToLogo"))

    if "compositionTextEnabled" in patch:
        comp["text"]["enabled"] = bool(patch.get("compositionTextEnabled"))
    if "albumEnabled" in patch:
        out["albumEnabled"] = bool(patch.get("albumEnabled"))
    if "titleEnabled" in patch:
        out["titleEnabled"] = bool(patch.get("titleEnabled"))
    if "albumManualText" in patch:
        out["albumManualText"] = str(patch.get("albumManualText") or "")
    if "titleManualText" in patch:
        out["titleManualText"] = str(patch.get("titleManualText") or "")

    if "compositionOverlayEnabled" in patch:
        comp["overlay"]["enabled"] = bool(patch.get("compositionOverlayEnabled"))
    if "compositionOverlayAnimation" in patch:
        anim = normalize_animation_behavior_id(patch.get("compositionOverlayAnimation"))
        comp["overlay"]["animation"] = anim or NONE
    if "overlayStyle" in patch:
        style = str(patch.get("overlayStyle") or "film_grain").strip().lower()
        allowed = {"film_grain", "vhs", "glitch", "scanlines", "light_leak", "dust"}
        out["overlayStyle"] = style if style in allowed else "film_grain"

    if "compositionParticleType" in patch:
        ptype = normalize_particle_type_id(patch.get("compositionParticleType"))
        comp["particles"]["type"] = ptype or NONE
    if "compositionParticleBehavior" in patch:
        pbeh = normalize_animation_behavior_id(patch.get("compositionParticleBehavior"))
        comp["particles"]["behavior"] = pbeh or NONE
    if "particlesEnabled" in patch and not bool(patch.get("particlesEnabled")):
        comp["particles"]["type"] = NONE

    if "compositionLightingEffect" in patch:
        effect = normalize_lighting_effect_id(patch.get("compositionLightingEffect"))
        comp["lighting"]["effect"] = effect or NONE
    if "compositionLightingTrigger" in patch:
        trigger = normalize_lighting_trigger_id(patch.get("compositionLightingTrigger"))
        comp["lighting"]["trigger"] = trigger or NONE

    if "compositionCameraBehavior" in patch:
        cam = normalize_camera_behavior_id(patch.get("compositionCameraBehavior"))
        comp["camera"]["behavior"] = cam or NONE

    if "compositionPostEffects" in patch:
        comp["postProcessing"]["effects"] = normalize_post_effects_list(
            patch.get("compositionPostEffects")
        )
    if "compositionPostEffectsAppend" in patch:
        current = list(comp["postProcessing"].get("effects") or [])
        current.append(patch.get("compositionPostEffectsAppend"))
        comp["postProcessing"]["effects"] = normalize_post_effects_list(current)

    if "audioPath" in patch or "compositionAudioPath" in patch:
        path = str(patch.get("audioPath") or patch.get("compositionAudioPath") or "").strip() or None
        assets["audio"] = path

    if "compositionAudioMapping" in patch:
        comp["audio"]["mapping"] = normalize_audio_mapping(patch.get("compositionAudioMapping"))

    if "name" in patch:
        name = str(patch.get("name") or "").strip() or out["name"]
        out["name"] = name
        out["templateName"] = name

    out["composition"] = comp
    out["assets"] = assets
    return out


def inspector_bind_state(doc: dict[str, Any]) -> dict[str, Any]:
    """Flat bind dict for Studio inspectors."""
    scene = normalize_studio_document(doc)
    comp = scene["composition"]
    assets = scene["assets"]
    return {
        "compositionColorPalette": comp.get("colorPalette") or NONE,
        "compositionBackgroundMotion": comp["background"].get("motion") or "static",
        "compositionBackgroundAtmosphere": comp["background"].get("atmosphere") or NONE,
        "backgroundEnabled": bool(assets.get("backgroundImage") or comp["background"].get("image")),
        "backgroundImage": assets.get("backgroundImage") or "",
        "compositionSpectrumShape": comp["spectrum"]["shape"],
        "compositionSpectrumMaterial": comp["spectrum"]["material"],
        "compositionSpectrumAnimation": comp["spectrum"]["animation"],
        "spectrumEnabled": comp["spectrum"]["shape"] not in (None, "", NONE),
        "compositionLogoAnimation": comp["logo"]["animation"],
        "logoEnabled": bool(comp["logo"].get("enabled", True)),
        "logoPath": assets.get("logo") or "",
        "spectrumAttachToLogo": bool(scene.get("spectrumAttachToLogo", False)),
        "compositionTextEnabled": bool(comp["text"].get("enabled", False)),
        "albumEnabled": bool(scene.get("albumEnabled", False)),
        "titleEnabled": bool(scene.get("titleEnabled", False)),
        "albumManualText": str(scene.get("albumManualText") or ""),
        "titleManualText": str(scene.get("titleManualText") or ""),
        "compositionOverlayEnabled": bool(comp["overlay"].get("enabled", False)),
        "compositionOverlayAnimation": comp["overlay"].get("animation") or NONE,
        "overlayStyle": str(scene.get("overlayStyle") or "film_grain"),
        "studioMode": str(scene.get("studioMode") or "creator"),
        "compositionParticleType": comp["particles"]["type"],
        "compositionParticleBehavior": comp["particles"]["behavior"],
        "particlesEnabled": comp["particles"]["type"] not in (None, "", NONE),
        "compositionLightingEffect": comp["lighting"].get("effect") or NONE,
        "compositionLightingTrigger": comp["lighting"].get("trigger") or NONE,
        "compositionCameraBehavior": comp["camera"].get("behavior") or NONE,
        "compositionPostEffects": list(comp["postProcessing"].get("effects") or []),
        "compositionAudioMapping": dict(comp["audio"].get("mapping") or {}),
        "audioPath": assets.get("audio") or "",
        "name": scene.get("name") or "Untitled Composition",
    }
