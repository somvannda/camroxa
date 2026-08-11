"""Studio scene document helpers — camxora.composition as v1 authority."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer_studio.composition_effects.audio_mapping import normalize_audio_mapping
from visualizer_studio.presets.animations import (
    list_animation_behavior_options,
    normalize_animation_behavior_id,
)
from visualizer_studio.presets.atmosphere import list_atmosphere_options, normalize_atmosphere_id
from visualizer_studio.presets.audio_buses import (
    list_audio_bus_options,
    list_audio_mapping_target_options,
)
from visualizer_studio.presets.background_motion import (
    list_background_motion_options,
    normalize_background_motion_id,
)
from visualizer_studio.presets.camera import list_camera_behavior_options, normalize_camera_behavior_id
from visualizer_studio.presets.lighting import (
    list_lighting_effect_options,
    list_lighting_trigger_options,
    normalize_lighting_effect_id,
    normalize_lighting_trigger_id,
)
from visualizer_studio.presets.materials import (
    list_spectrum_material_options,
    normalize_spectrum_material_id,
)
from visualizer_studio.presets.palettes import list_color_palette_options, normalize_color_palette_id
from visualizer_studio.presets.particles import list_particle_type_options, normalize_particle_type_id
from visualizer_studio.presets.post import list_post_effect_options, normalize_post_effects_list
from visualizer_studio.presets.shapes import list_spectrum_shape_options, normalize_spectrum_shape_id
from visualizer_studio.scene import NONE, default_document, normalize_assets, normalize_composition


SCENE_TREE_NODES: tuple[tuple[str, str], ...] = (
    ("palette", "Color Palette"),
    ("background", "Background"),
    ("spectrum", "Spectrum"),
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


def _audio_tracks(assets: dict[str, Any]) -> list[str]:
    raw = assets.get("audioTracks")
    tracks: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            path = str(item or "").strip()
            if path and path not in tracks:
                tracks.append(path)
    return tracks


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
    # Studio has a single full view (legacy mode field kept for older project files).
    doc["studioMode"] = "studio"
    export_raw = raw.get("studioExport") if isinstance(raw.get("studioExport"), dict) else {}
    doc["studioExport"] = _normalize_studio_export(export_raw)
    return doc


def _normalize_studio_export(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    resolution = str(src.get("resolution") or "1920x1080").strip() or "1920x1080"
    try:
        fps = int(src.get("fps") or 24)
    except (TypeError, ValueError):
        fps = 24
    if fps not in {24, 30, 48, 60}:
        fps = min({24, 30, 48, 60}, key=lambda choice: abs(choice - fps))
    quality = str(src.get("quality") or "fast").strip().lower()
    if quality == "quality":
        quality = "balanced"
    if quality not in {"very_fast", "fast", "balanced"}:
        quality = "fast"
    try:
        range_start = max(0.0, float(src.get("rangeStart") or 0.0))
    except (TypeError, ValueError):
        range_start = 0.0
    try:
        range_end = max(0.0, float(src.get("rangeEnd") or 0.0))
    except (TypeError, ValueError):
        range_end = 0.0
    return {
        "resolution": resolution,
        "fps": fps,
        "quality": quality,
        "includeAudio": bool(src.get("includeAudio", True)),
        "rangeStart": range_start,
        "rangeEnd": range_end,
    }


def apply_axis_patch(doc: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply inspector axis patches onto a studio document (immutable-style copy)."""
    out = deepcopy(normalize_studio_document(doc))
    comp = out["composition"]
    assets = out["assets"]

    if "compositionColorPalette" in patch:
        palette = normalize_color_palette_id(patch.get("compositionColorPalette"))
        comp["colorPalette"] = palette
    for key, dest, lo, hi in (
        ("compositionPaletteIntensity", "paletteIntensity", 0.0, 2.0),
        ("compositionPaletteSaturation", "paletteSaturation", 0.0, 2.0),
    ):
        if key in patch:
            try:
                comp[dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass

    if "compositionBackgroundMotion" in patch:
        motion = normalize_background_motion_id(patch.get("compositionBackgroundMotion"))
        comp["background"]["motion"] = motion or "static"
    if "compositionBackgroundAtmosphere" in patch:
        atm = normalize_atmosphere_id(patch.get("compositionBackgroundAtmosphere"))
        comp["background"]["atmosphere"] = atm or NONE
    if "backgroundEnabled" in patch and not bool(patch.get("backgroundEnabled")):
        # Disable clears the path so bind-state stays consistent.
        assets["backgroundImage"] = None
        assets["backgroundVideo"] = None
        comp["background"]["image"] = None

    if "backgroundImage" in patch or "compositionBackgroundImage" in patch:
        path = str(
            patch.get("backgroundImage") or patch.get("compositionBackgroundImage") or ""
        ).strip() or None
        assets["backgroundImage"] = path
        comp["background"]["image"] = path
        if path:
            assets["backgroundVideo"] = None

    if "backgroundVideo" in patch:
        path = str(patch.get("backgroundVideo") or "").strip() or None
        assets["backgroundVideo"] = path

    if "compositionBackgroundBrightness" in patch:
        try:
            comp["background"]["brightness"] = max(
                0.2, min(2.0, float(patch.get("compositionBackgroundBrightness")))
            )
        except (TypeError, ValueError):
            pass
    if "compositionBackgroundContrast" in patch:
        try:
            comp["background"]["contrast"] = max(
                0.2, min(2.0, float(patch.get("compositionBackgroundContrast")))
            )
        except (TypeError, ValueError):
            pass
    if "compositionBackgroundReactivity" in patch:
        try:
            comp["background"]["reactivity"] = max(
                0.0, min(1.0, float(patch.get("compositionBackgroundReactivity")))
            )
        except (TypeError, ValueError):
            pass
    for key, dest, lo, hi in (
        ("compositionBackgroundSaturation", "saturation", 0.0, 2.0),
        ("compositionBackgroundHue", "hue", -180.0, 180.0),
        ("compositionBackgroundSmoothing", "smoothing", 0.0, 0.99),
        ("compositionBackgroundMotionSpeed", "motionSpeed", 0.15, 3.0),
        ("compositionBackgroundMotionAmplitude", "motionAmplitude", 0.15, 3.0),
        ("compositionBackgroundMotionZoom", "motionZoom", 0.15, 3.0),
        ("compositionBackgroundMotionWarp", "motionWarp", 0.0, 3.0),
        ("compositionBackgroundAtmosphereDensity", "atmosphereDensity", 0.0, 2.5),
        ("compositionBackgroundAtmosphereSpeed", "atmosphereSpeed", 0.1, 3.0),
        ("compositionBackgroundAtmosphereOpacity", "atmosphereOpacity", 0.0, 1.0),
        ("compositionBackgroundAtmosphereWind", "atmosphereWind", 0.0, 3.0),
    ):
        if key in patch:
            try:
                comp["background"][dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass

    if "compositionSpectrumShape" in patch:
        shape = normalize_spectrum_shape_id(patch.get("compositionSpectrumShape"))
        comp["spectrum"]["shape"] = shape or NONE
        # Manual shape changes leave Custom look so we don't keep fighting the stack.
        if "compositionSpectrumLook" not in patch:
            comp["spectrum"]["look"] = None
    if "compositionSpectrumLook" in patch:
        from features.studio.lib.spectrum_looks import normalize_spectrum_look_id

        comp["spectrum"]["look"] = normalize_spectrum_look_id(patch.get("compositionSpectrumLook"))
    if "compositionSpectrumMaterial" in patch:
        material = normalize_spectrum_material_id(patch.get("compositionSpectrumMaterial"))
        comp["spectrum"]["material"] = material or NONE
    if "compositionSpectrumAnimation" in patch:
        anim = normalize_animation_behavior_id(patch.get("compositionSpectrumAnimation"))
        comp["spectrum"]["animation"] = anim or NONE
    if "spectrumEnabled" in patch and not bool(patch.get("spectrumEnabled")):
        comp["spectrum"]["shape"] = NONE
    for key, dest, lo, hi in (
        ("compositionSpectrumBarHeight", "barHeight", 0.25, 4.0),
        ("compositionSpectrumGlow", "glow", 0.0, 1.0),
        ("compositionSpectrumOpacity", "opacity", 0.1, 1.0),
        ("compositionSpectrumBlur", "blur", 0.0, 8.0),
        ("compositionSpectrumBarWidthScale", "barWidthScale", 0.08, 3.0),
        ("compositionSpectrumThicknessScale", "thicknessScale", 0.25, 3.0),
        ("compositionSpectrumSizeScale", "sizeScale", 0.35, 2.5),
        ("compositionSpectrumTipTaper", "tipTaper", 0.0, 1.0),
        ("compositionSpectrumAnimationSpeed", "animationSpeed", 0.15, 3.0),
        ("compositionSpectrumAnimationScale", "animationScaleAmount", 0.0, 2.5),
        ("compositionSpectrumAnimationOpacity", "animationOpacityAmount", 0.0, 2.5),
        ("compositionSpectrumAnimationRotate", "animationRotateAmount", 0.0, 2.5),
        ("compositionSpectrumAnimationAudio", "animationAudioAmount", 0.0, 2.5),
        ("compositionSpectrumAnimationKick", "animationKick", 0.0, 2.5),
        ("compositionSpectrumOffsetX", "offsetX", -2.0, 2.0),
        ("compositionSpectrumOffsetY", "offsetY", -2.0, 2.0),
    ):
        if key in patch:
            try:
                comp["spectrum"][dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass
    if "compositionSpectrumRotationDeg" in patch:
        try:
            rot = float(patch.get("compositionSpectrumRotationDeg") or 0.0) % 360.0
            if rot < 0.0:
                rot += 360.0
            comp["spectrum"]["rotationDeg"] = float(rot)
        except (TypeError, ValueError):
            pass
    if "compositionSpectrumAnimationSmoothing" in patch:
        raw_s = patch.get("compositionSpectrumAnimationSmoothing")
        if raw_s in (None, "", "auto", "none"):
            comp["spectrum"]["animationSmoothing"] = None
        else:
            try:
                comp["spectrum"]["animationSmoothing"] = max(0.1, min(1.0, float(raw_s)))
            except (TypeError, ValueError):
                pass
    if "compositionSpectrumBarCount" in patch:
        try:
            comp["spectrum"]["barCount"] = int(
                round(max(24, min(160, float(patch.get("compositionSpectrumBarCount")))))
            )
        except (TypeError, ValueError):
            pass
    if "compositionSpectrumMirrored" in patch:
        raw_m = patch.get("compositionSpectrumMirrored")
        if raw_m in (None, "", "none", "auto"):
            comp["spectrum"]["mirrored"] = None
        else:
            comp["spectrum"]["mirrored"] = bool(raw_m)
    if "compositionSpectrumGravity" in patch:
        raw_g = patch.get("compositionSpectrumGravity")
        if raw_g in (None, "", "none", "auto"):
            comp["spectrum"]["gravity"] = None
        else:
            from visualizer_studio._spectrum_fast import normalize_spectrum_gravity

            comp["spectrum"]["gravity"] = normalize_spectrum_gravity(raw_g)
    if "compositionSpectrumPeakCaps" in patch:
        comp["spectrum"]["peakCapsEnabled"] = bool(patch.get("compositionSpectrumPeakCaps"))
    if "compositionSpectrumSolidBand" in patch:
        comp["spectrum"]["solidBand"] = bool(patch.get("compositionSpectrumSolidBand"))
    if "compositionSpectrumColorPalette" in patch:
        pal = normalize_color_palette_id(patch.get("compositionSpectrumColorPalette"))
        comp["spectrum"]["colorPalette"] = pal  # None = inherit global palette
    if "compositionSpectrumGradientColors" in patch:
        raw_stops = patch.get("compositionSpectrumGradientColors")
        if isinstance(raw_stops, list) and len(raw_stops) >= 2:
            from features.video.lib.spectrum_color_engine import normalize_spectrum_gradient_colors

            comp["spectrum"]["gradientColors"] = normalize_spectrum_gradient_colors(
                [str(c) for c in raw_stops],
                "#ff4fd8",
            )
        elif raw_stops in (None, [], "none", "clear"):
            comp["spectrum"]["gradientColors"] = None

    from visualizer_studio.scene.spectrum_layers import (
        default_spectrum_layer,
        normalize_spectrum_layers,
        spectrum_layer_defaults_from_comp,
    )

    def _norm_layers(raw: object) -> list:
        return normalize_spectrum_layers(raw, defaults=comp["spectrum"])

    # Global spectrum knobs (inspector) push onto every ring unless a later
    # compositionSpectrumLayerPatch overrides a single layer.
    _spectrum_to_layer: dict[str, str] = {
        "compositionSpectrumBarCount": "barCount",
        "compositionSpectrumTipTaper": "tipTaper",
        "compositionSpectrumBarWidthScale": "barWidthScale",
        "compositionSpectrumThicknessScale": "thicknessScale",
        "compositionSpectrumBarHeight": "barHeight",
        "compositionSpectrumPeakCaps": "peakCapsEnabled",
        "compositionSpectrumSolidBand": "solidBand",
    }
    if any(key in patch for key in _spectrum_to_layer):
        layers = _norm_layers(comp["spectrum"].get("layers"))
        for layer in layers:
            for patch_key, layer_key in _spectrum_to_layer.items():
                if patch_key in patch and layer_key in comp["spectrum"]:
                    layer[layer_key] = comp["spectrum"][layer_key]
        comp["spectrum"]["layers"] = layers

    if "compositionSpectrumLayers" in patch:
        comp["spectrum"]["layers"] = _norm_layers(patch.get("compositionSpectrumLayers"))
    if "compositionSpectrumLayerIndex" in patch:
        layers = _norm_layers(comp["spectrum"].get("layers"))
        try:
            idx = int(patch.get("compositionSpectrumLayerIndex") or 0)
        except (TypeError, ValueError):
            idx = 0
        comp["spectrum"]["layers"] = layers
        comp["spectrum"]["selectedLayerIndex"] = max(0, min(len(layers) - 1, idx))
    if "compositionSpectrumLayerPatch" in patch and isinstance(patch.get("compositionSpectrumLayerPatch"), dict):
        layers = _norm_layers(comp["spectrum"].get("layers"))
        try:
            idx = int(comp["spectrum"].get("selectedLayerIndex") or 0)
        except (TypeError, ValueError):
            idx = 0
        idx = max(0, min(len(layers) - 1, idx))
        if "compositionSpectrumLayerIndex" in patch:
            try:
                idx = max(0, min(len(layers) - 1, int(patch.get("compositionSpectrumLayerIndex"))))
            except (TypeError, ValueError):
                pass
        merged = dict(layers[idx])
        merged.update(patch["compositionSpectrumLayerPatch"])
        layers[idx] = _norm_layers([merged])[0]
        comp["spectrum"]["layers"] = layers
        comp["spectrum"]["selectedLayerIndex"] = idx
    if "compositionSpectrumLayerAdd" in patch:
        layers = _norm_layers(comp["spectrum"].get("layers"))
        seed = spectrum_layer_defaults_from_comp(comp["spectrum"])
        basis = dict(layers[-1]) if layers else default_spectrum_layer(0, defaults=seed)
        try:
            max_gap = max(float(x.get("radiusOffset") or 0.0) for x in layers) if layers else 0.0
        except (TypeError, ValueError):
            max_gap = 0.0
        layers.append(
            {
                **basis,
                "name": f"Ring {len(layers) + 1}",
                "radiusOffset": max_gap + 18.0,
                "opacity": float(basis.get("opacity") or 1.0) or 1.0,
                "enabled": True,
            }
        )
        comp["spectrum"]["layers"] = _norm_layers(layers)
        comp["spectrum"]["selectedLayerIndex"] = len(comp["spectrum"]["layers"]) - 1
    if "compositionSpectrumLayerDuplicate" in patch:
        layers = _norm_layers(comp["spectrum"].get("layers"))
        try:
            idx = int(comp["spectrum"].get("selectedLayerIndex") or 0)
        except (TypeError, ValueError):
            idx = 0
        idx = max(0, min(len(layers) - 1, idx))
        basis = dict(layers[idx])
        layers.append(
            {
                **basis,
                "name": f"{basis.get('name') or 'Ring'} Copy",
                "radiusOffset": float(basis.get("radiusOffset") or 0.0) + 12.0,
            }
        )
        comp["spectrum"]["layers"] = _norm_layers(layers)
        comp["spectrum"]["selectedLayerIndex"] = len(comp["spectrum"]["layers"]) - 1
    if "compositionSpectrumLayerDelete" in patch:
        layers = _norm_layers(comp["spectrum"].get("layers"))
        if len(layers) >= 2:
            try:
                idx = int(comp["spectrum"].get("selectedLayerIndex") or 0)
            except (TypeError, ValueError):
                idx = 0
            idx = max(0, min(len(layers) - 1, idx))
            layers.pop(idx)
            comp["spectrum"]["layers"] = _norm_layers(layers)
            comp["spectrum"]["selectedLayerIndex"] = max(0, min(len(comp["spectrum"]["layers"]) - 1, idx - 1))
    if "compositionSpectrumLayerMove" in patch:
        layers = _norm_layers(comp["spectrum"].get("layers"))
        direction = str(patch.get("compositionSpectrumLayerMove") or "").strip().lower()
        try:
            idx = int(comp["spectrum"].get("selectedLayerIndex") or 0)
        except (TypeError, ValueError):
            idx = 0
        idx = max(0, min(len(layers) - 1, idx))
        if direction == "up" and idx > 0:
            layers[idx - 1], layers[idx] = layers[idx], layers[idx - 1]
            idx -= 1
        elif direction == "down" and idx < len(layers) - 1:
            layers[idx + 1], layers[idx] = layers[idx], layers[idx + 1]
            idx += 1
        comp["spectrum"]["layers"] = layers
        comp["spectrum"]["selectedLayerIndex"] = idx
    if "compositionSpectrumPositionPx" in patch and isinstance(patch.get("compositionSpectrumPositionPx"), dict):
        pos = patch["compositionSpectrumPositionPx"]
        try:
            # Convert preview pixel offsets (center-relative) back to normalized.
            # Wide range so drag feels free across the full preview.
            comp["spectrum"]["offsetX"] = max(-2.0, min(2.0, float(pos.get("x") or 0.0) / 480.0))
            comp["spectrum"]["offsetY"] = max(-2.0, min(2.0, float(pos.get("y") or 0.0) / 270.0))
        except (TypeError, ValueError):
            pass

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
    if "compositionLogoScale" in patch:
        try:
            comp["logo"]["scale"] = max(0.25, min(3.0, float(patch.get("compositionLogoScale"))))
        except (TypeError, ValueError):
            pass
    if "compositionLogoOpacity" in patch:
        try:
            comp["logo"]["opacity"] = max(0.1, min(1.0, float(patch.get("compositionLogoOpacity"))))
        except (TypeError, ValueError):
            pass
    if "compositionLogoCircleMask" in patch:
        comp["logo"]["circleMask"] = bool(patch.get("compositionLogoCircleMask"))
    if "compositionLogoFitToShape" in patch:
        comp["logo"]["fitToShape"] = bool(patch.get("compositionLogoFitToShape"))
    if "compositionLogoMaskShape" in patch:
        try:
            from visualizer_studio.logo_mask import normalize_logo_mask_shape_id

            comp["logo"]["maskShape"] = normalize_logo_mask_shape_id(
                patch.get("compositionLogoMaskShape")
            )
        except Exception:
            pass
    if "compositionLogoContainInShape" in patch:
        contain = bool(patch.get("compositionLogoContainInShape"))
        comp["logo"]["containInShape"] = contain
        if contain:
            # Lock logo to spectrum path: shared center + size clamp.
            out["spectrumAttachToLogo"] = True
            comp["logo"]["offsetX"] = 0.0
            comp["logo"]["offsetY"] = 0.0
    if "compositionLogoRotationDeg" in patch:
        try:
            rot = float(patch.get("compositionLogoRotationDeg") or 0.0) % 360.0
            if rot < 0.0:
                rot += 360.0
            comp["logo"]["rotationDeg"] = float(rot)
        except (TypeError, ValueError):
            pass
    for key, dest, lo, hi in (
        ("compositionLogoReactivity", "reactivity", 0.0, 1.0),
        ("compositionLogoOffsetX", "offsetX", -0.5, 0.5),
        ("compositionLogoOffsetY", "offsetY", -0.5, 0.5),
        ("compositionLogoSize", "size", 64.0, 512.0),
    ):
        if key in patch:
            try:
                comp["logo"][dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass

    if "compositionTextEnabled" in patch:
        comp["text"]["enabled"] = bool(patch.get("compositionTextEnabled"))
    for key, dest, lo, hi in (
        ("compositionTextOpacity", "opacity", 0.1, 1.0),
        ("compositionTextScale", "scale", 0.5, 2.5),
        ("compositionTextOffsetY", "offsetY", -0.4, 0.4),
    ):
        if key in patch:
            try:
                comp["text"][dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass
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
    if "compositionOverlayAmount" in patch:
        try:
            comp["overlay"]["amount"] = max(
                0.05, min(1.0, float(patch.get("compositionOverlayAmount")))
            )
        except (TypeError, ValueError):
            pass

    if "compositionParticleType" in patch:
        ptype = normalize_particle_type_id(patch.get("compositionParticleType"))
        comp["particles"]["type"] = ptype or NONE
    if "compositionParticleBehavior" in patch:
        pbeh = normalize_animation_behavior_id(patch.get("compositionParticleBehavior"))
        comp["particles"]["behavior"] = pbeh or NONE
    if "particlesEnabled" in patch and not bool(patch.get("particlesEnabled")):
        comp["particles"]["type"] = NONE
    for key, dest, lo, hi in (
        ("compositionParticleSpawn", "spawn", 0.1, 3.0),
        ("compositionParticleSize", "size", 0.25, 4.0),
        ("compositionParticleOpacity", "opacity", 0.05, 1.0),
        ("compositionParticleSpeed", "speed", 0.25, 3.0),
        ("compositionParticleReactivity", "reactivity", 0.0, 1.0),
    ):
        if key in patch:
            try:
                comp["particles"][dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass

    if "compositionLightingEffect" in patch:
        effect = normalize_lighting_effect_id(patch.get("compositionLightingEffect"))
        comp["lighting"]["effect"] = effect or NONE
    if "compositionLightingTrigger" in patch:
        trigger = normalize_lighting_trigger_id(patch.get("compositionLightingTrigger"))
        comp["lighting"]["trigger"] = trigger or NONE
    for key, dest, lo, hi in (
        ("compositionLightingIntensity", "intensity", 0.1, 1.5),
        ("compositionLightingThickness", "thickness", 0.5, 3.0),
        ("compositionLightingGlow", "glow", 0.0, 1.0),
        ("compositionLightingFlashRate", "flashRate", 0.1, 2.0),
        ("compositionLightingSpeed", "speed", 0.25, 3.0),
    ):
        if key in patch:
            try:
                comp["lighting"][dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass

    if "compositionCameraBehavior" in patch:
        cam = normalize_camera_behavior_id(patch.get("compositionCameraBehavior"))
        comp["camera"]["behavior"] = cam or NONE
    for key, dest, lo, hi in (
        ("compositionCameraZoomBias", "zoomBias", 0.7, 1.6),
        ("compositionCameraPanX", "panX", -0.5, 0.5),
        ("compositionCameraPanY", "panY", -0.5, 0.5),
        ("compositionCameraShakeAmount", "shakeAmount", 0.0, 1.0),
        ("compositionCameraRollBias", "rollBias", -15.0, 15.0),
    ):
        if key in patch:
            try:
                comp["camera"][dest] = max(lo, min(hi, float(patch.get(key))))
            except (TypeError, ValueError):
                pass

    if "compositionPostEffects" in patch:
        comp["postProcessing"]["effects"] = normalize_post_effects_list(
            patch.get("compositionPostEffects")
        )
    if "compositionPostEffectsAppend" in patch:
        current = list(comp["postProcessing"].get("effects") or [])
        current.append(patch.get("compositionPostEffectsAppend"))
        comp["postProcessing"]["effects"] = normalize_post_effects_list(current)
    if "compositionPostAmount" in patch:
        try:
            comp["postProcessing"]["amount"] = max(
                0.05, min(1.0, float(patch.get("compositionPostAmount")))
            )
        except (TypeError, ValueError):
            pass
    if "compositionPerformanceQuality" in patch:
        q = str(patch.get("compositionPerformanceQuality") or "medium").strip().lower()
        comp.setdefault("performance", {})
        comp["performance"]["quality"] = q if q in {"low", "medium", "high"} else "medium"
    if "compositionPerformanceLod" in patch:
        comp.setdefault("performance", {})
        comp["performance"]["lod"] = bool(patch.get("compositionPerformanceLod"))

    if "audioTracks" in patch and isinstance(patch.get("audioTracks"), list):
        tracks = []
        for item in patch["audioTracks"]:
            path = str(item or "").strip()
            if path and path not in tracks:
                tracks.append(path)
        assets["audioTracks"] = tracks
        active = str(assets.get("audio") or "").strip()
        if not active or active not in tracks:
            assets["audio"] = tracks[0] if tracks else None

    if "audioPath" in patch or "compositionAudioPath" in patch:
        path = str(patch.get("audioPath") or patch.get("compositionAudioPath") or "").strip() or None
        assets["audio"] = path
        tracks = _audio_tracks(assets)
        if path and path not in tracks:
            tracks.append(path)
        assets["audioTracks"] = tracks

    if "removeAudioTrack" in patch:
        remove = str(patch.get("removeAudioTrack") or "").strip()
        tracks = [p for p in _audio_tracks(assets) if p != remove]
        assets["audioTracks"] = tracks
        if str(assets.get("audio") or "") == remove:
            assets["audio"] = tracks[0] if tracks else None

    if "compositionAudioMapping" in patch:
        comp["audio"]["mapping"] = normalize_audio_mapping(patch.get("compositionAudioMapping"))
    if "compositionAudioGain" in patch:
        try:
            comp["audio"]["gain"] = max(0.25, min(3.0, float(patch.get("compositionAudioGain"))))
        except (TypeError, ValueError):
            pass
    if "compositionAudioSmoothing" in patch:
        try:
            comp["audio"]["smoothing"] = max(
                0.0, min(0.99, float(patch.get("compositionAudioSmoothing")))
            )
        except (TypeError, ValueError):
            pass
    if "compositionAudioBassEmphasis" in patch:
        try:
            comp["audio"]["bassEmphasis"] = max(
                0.5, min(2.0, float(patch.get("compositionAudioBassEmphasis")))
            )
        except (TypeError, ValueError):
            pass

    if "name" in patch:
        name = str(patch.get("name") or "").strip() or out["name"]
        out["name"] = name
        out["templateName"] = name

    if "studioExport" in patch and isinstance(patch.get("studioExport"), dict):
        merged = dict(out.get("studioExport") or {})
        merged.update(patch["studioExport"])
        out["studioExport"] = _normalize_studio_export(merged)

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
        "compositionPaletteIntensity": float(comp.get("paletteIntensity") or 1.0),
        "compositionPaletteSaturation": float(comp.get("paletteSaturation") or 1.0),
        "compositionBackgroundMotion": comp["background"].get("motion") or "static",
        "compositionBackgroundAtmosphere": comp["background"].get("atmosphere") or NONE,
        "backgroundEnabled": bool(
            assets.get("backgroundImage")
            or assets.get("backgroundVideo")
            or comp["background"].get("image")
        ),
        "backgroundImage": assets.get("backgroundImage") or "",
        "backgroundVideo": assets.get("backgroundVideo") or "",
        "compositionBackgroundBrightness": float(comp["background"].get("brightness") or 1.0),
        "compositionBackgroundContrast": float(comp["background"].get("contrast") or 1.0),
        "compositionBackgroundReactivity": float(comp["background"].get("reactivity") or 0.0),
        "compositionBackgroundSaturation": float(comp["background"].get("saturation") or 1.0),
        "compositionBackgroundHue": float(comp["background"].get("hue") or 0.0),
        "compositionBackgroundSmoothing": float(comp["background"].get("smoothing") or 0.8),
        "compositionBackgroundMotionSpeed": float(comp["background"].get("motionSpeed") or 1.0),
        "compositionBackgroundMotionAmplitude": float(comp["background"].get("motionAmplitude") or 1.0),
        "compositionBackgroundMotionZoom": float(comp["background"].get("motionZoom") or 1.0),
        "compositionBackgroundMotionWarp": float(comp["background"].get("motionWarp") or 1.0),
        "compositionBackgroundAtmosphereDensity": float(comp["background"].get("atmosphereDensity") or 1.0),
        "compositionBackgroundAtmosphereSpeed": float(comp["background"].get("atmosphereSpeed") or 1.0),
        "compositionBackgroundAtmosphereOpacity": float(comp["background"].get("atmosphereOpacity") or 1.0),
        "compositionBackgroundAtmosphereWind": float(comp["background"].get("atmosphereWind") or 1.0),
        "compositionSpectrumShape": comp["spectrum"]["shape"],
        "compositionSpectrumLook": comp["spectrum"].get("look") or "none",
        "compositionSpectrumMaterial": comp["spectrum"]["material"],
        "compositionSpectrumAnimation": comp["spectrum"]["animation"],
        "compositionSpectrumBarHeight": float(comp["spectrum"].get("barHeight") or 1.0),
        # Use None-check — ``0.0 or 0.45`` wrongly snaps Glow back to 0.45.
        "compositionSpectrumGlow": float(
            0.45 if comp["spectrum"].get("glow") is None else comp["spectrum"].get("glow")
        ),
        "compositionSpectrumOpacity": float(comp["spectrum"].get("opacity") or 1.0),
        "compositionSpectrumBlur": float(
            0.0 if comp["spectrum"].get("blur") is None else comp["spectrum"].get("blur")
        ),
        "compositionSpectrumBarWidthScale": float(comp["spectrum"].get("barWidthScale") or 1.0),
        "compositionSpectrumThicknessScale": float(comp["spectrum"].get("thicknessScale") or 1.0),
        "compositionSpectrumSizeScale": float(comp["spectrum"].get("sizeScale") or 1.0),
        "compositionSpectrumTipTaper": float(
            0.0 if comp["spectrum"].get("tipTaper") is None else comp["spectrum"].get("tipTaper")
        ),
        "compositionSpectrumAnimationSpeed": float(
            1.0
            if comp["spectrum"].get("animationSpeed") is None
            else comp["spectrum"].get("animationSpeed")
        ),
        "compositionSpectrumAnimationScale": float(
            1.0
            if comp["spectrum"].get("animationScaleAmount") is None
            else comp["spectrum"].get("animationScaleAmount")
        ),
        "compositionSpectrumAnimationOpacity": float(
            1.0
            if comp["spectrum"].get("animationOpacityAmount") is None
            else comp["spectrum"].get("animationOpacityAmount")
        ),
        "compositionSpectrumAnimationRotate": float(
            1.0
            if comp["spectrum"].get("animationRotateAmount") is None
            else comp["spectrum"].get("animationRotateAmount")
        ),
        "compositionSpectrumAnimationAudio": float(
            1.0
            if comp["spectrum"].get("animationAudioAmount") is None
            else comp["spectrum"].get("animationAudioAmount")
        ),
        "compositionSpectrumAnimationKick": float(
            1.0
            if comp["spectrum"].get("animationKick") is None
            else comp["spectrum"].get("animationKick")
        ),
        "compositionSpectrumAnimationSmoothing": (
            None
            if comp["spectrum"].get("animationSmoothing") is None
            else float(comp["spectrum"].get("animationSmoothing"))
        ),
        "compositionSpectrumOffsetX": float(comp["spectrum"].get("offsetX") or 0.0),
        "compositionSpectrumOffsetY": float(comp["spectrum"].get("offsetY") or 0.0),
        "compositionSpectrumRotationDeg": float(comp["spectrum"].get("rotationDeg") or 0.0),
        "compositionSpectrumColorPalette": comp["spectrum"].get("colorPalette") or NONE,
        "compositionSpectrumGradientColors": list(comp["spectrum"].get("gradientColors") or []),
        "compositionSpectrumBarCount": int(comp["spectrum"].get("barCount") or 64),
        "compositionSpectrumMirrored": (
            "auto"
            if comp["spectrum"].get("mirrored") is None
            else bool(comp["spectrum"].get("mirrored"))
        ),
        "compositionSpectrumGravity": (
            "auto"
            if comp["spectrum"].get("gravity") in (None, "", "auto")
            else str(comp["spectrum"].get("gravity") or "auto")
        ),
        "compositionSpectrumPeakCaps": bool(comp["spectrum"].get("peakCapsEnabled", False)),
        "compositionSpectrumSolidBand": bool(comp["spectrum"].get("solidBand", False)),
        "compositionSpectrumLayers": list(comp["spectrum"].get("layers") or []),
        "compositionSpectrumLayerIndex": int(comp["spectrum"].get("selectedLayerIndex") or 0),
        "spectrumEnabled": comp["spectrum"]["shape"] not in (None, "", NONE),
        "compositionLogoAnimation": comp["logo"]["animation"],
        "compositionLogoScale": float(comp["logo"].get("scale") or 1.0),
        "compositionLogoOpacity": float(comp["logo"].get("opacity") or 1.0),
        "compositionLogoCircleMask": bool(comp["logo"].get("circleMask", False)),
        "compositionLogoFitToShape": bool(comp["logo"].get("fitToShape", True)),
        "compositionLogoMaskShape": str(comp["logo"].get("maskShape") or "auto"),
        "compositionLogoContainInShape": bool(comp["logo"].get("containInShape", False)),
        "compositionLogoReactivity": float(comp["logo"].get("reactivity") or 0.0),
        "compositionLogoOffsetX": float(comp["logo"].get("offsetX") or 0.0),
        "compositionLogoOffsetY": float(comp["logo"].get("offsetY") or 0.0),
        "compositionLogoSize": float(comp["logo"].get("size") or 192.0),
        "compositionLogoRotationDeg": float(comp["logo"].get("rotationDeg") or 0.0),
        "logoEnabled": bool(comp["logo"].get("enabled", True)),
        "logoPath": assets.get("logo") or "",
        "spectrumAttachToLogo": bool(scene.get("spectrumAttachToLogo", False)),
        "compositionTextEnabled": bool(comp["text"].get("enabled", False)),
        "compositionTextOpacity": float(comp["text"].get("opacity") or 1.0),
        "compositionTextScale": float(comp["text"].get("scale") or 1.0),
        "compositionTextOffsetY": float(comp["text"].get("offsetY") or 0.0),
        "albumEnabled": bool(scene.get("albumEnabled", False)),
        "titleEnabled": bool(scene.get("titleEnabled", False)),
        "albumManualText": str(scene.get("albumManualText") or ""),
        "titleManualText": str(scene.get("titleManualText") or ""),
        "compositionOverlayEnabled": bool(comp["overlay"].get("enabled", False)),
        "compositionOverlayAnimation": comp["overlay"].get("animation") or NONE,
        "compositionOverlayAmount": float(comp["overlay"].get("amount") or 0.28),
        "overlayStyle": str(scene.get("overlayStyle") or "film_grain"),
        "studioMode": "studio",
        "compositionParticleType": comp["particles"]["type"],
        "compositionParticleBehavior": comp["particles"]["behavior"],
        "compositionParticleSpawn": float(comp["particles"].get("spawn") or 1.0),
        "compositionParticleSize": float(comp["particles"].get("size") or 1.0),
        "compositionParticleOpacity": float(comp["particles"].get("opacity") or 0.35),
        "compositionParticleSpeed": float(comp["particles"].get("speed") or 1.0),
        "compositionParticleReactivity": float(comp["particles"].get("reactivity") or 0.45),
        "particlesEnabled": comp["particles"]["type"] not in (None, "", NONE),
        "compositionLightingEffect": comp["lighting"].get("effect") or NONE,
        "compositionLightingTrigger": comp["lighting"].get("trigger") or NONE,
        "compositionLightingIntensity": float(comp["lighting"].get("intensity") or 0.85),
        "compositionLightingThickness": float(comp["lighting"].get("thickness") or 1.0),
        "compositionLightingGlow": float(comp["lighting"].get("glow") or 0.55),
        "compositionLightingFlashRate": float(comp["lighting"].get("flashRate") or 0.85),
        "compositionLightingSpeed": float(comp["lighting"].get("speed") or 1.0),
        "compositionCameraBehavior": comp["camera"].get("behavior") or NONE,
        "compositionCameraZoomBias": float(comp["camera"].get("zoomBias") or 1.0),
        "compositionCameraPanX": float(comp["camera"].get("panX") or 0.0),
        "compositionCameraPanY": float(comp["camera"].get("panY") or 0.0),
        "compositionCameraShakeAmount": float(comp["camera"].get("shakeAmount") or 0.5),
        "compositionCameraRollBias": float(comp["camera"].get("rollBias") or 0.0),
        "compositionPostEffects": list(comp["postProcessing"].get("effects") or []),
        "compositionPostAmount": float(comp["postProcessing"].get("amount") or 0.35),
        "compositionPerformanceQuality": str(
            (comp.get("performance") or {}).get("quality") or "medium"
        ),
        "compositionPerformanceLod": bool((comp.get("performance") or {}).get("lod", True)),
        "compositionAudioMapping": dict(comp["audio"].get("mapping") or {}),
        "compositionAudioGain": float(comp["audio"].get("gain") or 1.0),
        "compositionAudioSmoothing": float(comp["audio"].get("smoothing") or 0.65),
        "compositionAudioBassEmphasis": float(comp["audio"].get("bassEmphasis") or 1.0),
        "audioPath": assets.get("audio") or "",
        "audioTracks": list(assets.get("audioTracks") or []),
        "name": scene.get("name") or "Untitled Composition",
        "studioExport": dict(scene.get("studioExport") or _normalize_studio_export({})),
    }
