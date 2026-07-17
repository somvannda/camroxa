"""Video template save patch builders — port of Electron domain patch + save assembly."""

from __future__ import annotations

import copy
from typing import Any

from features.video.lib.template_value_utils import to_number, to_record
from features.video.lib.video_template_draft import VideoTemplateDraft, clone_layer_records


def build_spectrum_template_patch(template: dict[str, Any], draft: VideoTemplateDraft) -> dict[str, Any]:
    current_audio = to_record(template.get("audioSettings"))
    current_position = to_record(template.get("position"))
    rest_audio = {
        key: value
        for key, value in current_audio.items()
        if key
        not in {
            "sensitivity",
            "heightBoost",
            "kickDrop",
            "smoothing",
            "wingMotionSpeed",
            "wingRelease",
            "inputGain",
            "barHeight",
            "bandContrast",
            "transientFocus",
            "kickImpact",
            "bassEmphasis",
            "trebleShimmer",
            "peakHoldBlend",
            "motionSmoothing",
            "flyingGlowWingMotionSpeed",
            "flyingGlowWingRelease",
        }
    }
    return {
        "style": draft["style"],
        "spectrumEnabled": draft["spectrumEnabled"],
        "previewBindings": {
            **to_record(template.get("previewBindings")),
            "spectrumAttachToLogo": draft["spectrumAttachToLogo"],
            "spectrumLogoGap": draft["spectrumLogoGap"],
        },
        "audioSettings": {
            **rest_audio,
            "inputGain": draft["audioInputGain"],
            "barHeight": draft["audioBarHeight"],
            "bandContrast": draft["audioBandContrast"],
            "transientFocus": draft["audioTransientFocus"],
            "kickImpact": draft["audioKickImpact"],
            "bassEmphasis": draft["audioBassEmphasis"],
            "trebleShimmer": draft["audioTrebleShimmer"],
            "peakHoldBlend": draft["audioPeakHoldBlend"],
            "motionSmoothing": draft["audioMotionSmoothing"],
            "flyingGlowWingMotionSpeed": draft["flyingGlowWingMotionSpeed"],
            "flyingGlowWingRelease": draft["flyingGlowWingRelease"],
        },
        "position": {
            **current_position,
            "anchor": draft["anchor"],
            "x": draft["positionX"],
            "y": draft["positionY"],
        },
    }


def build_background_template_patch(template: dict[str, Any], draft: VideoTemplateDraft) -> dict[str, Any]:
    current = to_record(template.get("backgroundSettings"))
    return {
        "backgroundSettings": {
            **current,
            "enabled": draft["backgroundEnabled"],
            "fitMode": draft["backgroundFitMode"],
            "userScale": draft["backgroundUserScale"],
            "brightness": draft["backgroundBrightness"],
            "contrast": draft.get("backgroundContrast", 1),
            "saturation": draft.get("backgroundSaturation", 1),
            "hue": draft.get("backgroundHue", 0),
            "reactivity": draft["backgroundReactivity"],
            "smoothing": draft["backgroundSmoothing"],
            "motionMode": draft["backgroundMotionMode"],
            "motionZoomStrength": draft["backgroundMotionZoomStrength"],
            "motionVibrateStrength": draft["backgroundMotionVibrateStrength"],
            "motionSpeed": draft["backgroundMotionSpeed"],
            "userOffsetX": to_number(current.get("userOffsetX"), 0),
            "userOffsetY": to_number(current.get("userOffsetY"), 0),
        }
    }


def build_atmosphere_template_patch(template: dict[str, Any], draft: VideoTemplateDraft) -> dict[str, Any]:
    current_effects = to_record(template.get("effects"))
    current_vignette = to_record(current_effects.get("vignette"))
    current_smoke = to_record(current_effects.get("smoke"))
    return {
        "effects": {
            **current_effects,
            "vignette": {
                **current_vignette,
                "enabled": draft["vignetteEnabled"],
                "strength": draft["vignetteStrength"],
                "feather": draft["vignetteFeather"],
                "opacity": draft["vignetteOpacity"],
                "color": draft["vignetteColor"],
            },
            "smoke": {
                **current_smoke,
                "enabled": draft["smokeEnabled"],
                "strength": draft["smokeStrength"],
                "blur": draft["smokeBlur"],
                "noise": draft["smokeNoise"],
                "speed": draft["smokeSpeed"],
                "opacity": draft["smokeOpacity"],
                "color": draft["smokeColor"],
            },
        }
    }


def build_logo_template_patch(template: dict[str, Any], draft: VideoTemplateDraft) -> dict[str, Any]:
    current = to_record(template.get("logoSettings"))
    logo_path = str(draft.get("logoPath", "")).strip()
    return {
        "logoPath": logo_path,
        "previewLogo": logo_path,
        "logoSettings": {
            **current,
            "enabled": draft["logoEnabled"],
            "spinEnabled": draft["logoSpinEnabled"],
            "spinDirection": draft["logoSpinDirection"],
            "spinSpeed": draft["logoSpinSpeed"],
            "circleMask": draft["logoShape"] == "circle",
            "size": round(float(draft["logoSizeStep"]) * 100.0, 2),
            "opacity": draft["logoOpacity"],
            "reactivity": draft["logoReactivity"],
            "smoothing": draft["logoSmoothing"],
            "motionMode": draft["logoMotionMode"],
            "motionZoomStrength": draft["logoMotionZoomStrength"],
            "motionVibrateStrength": draft["logoMotionVibrateStrength"],
            "motionSpeed": draft["logoMotionSpeed"],
        },
    }


def build_particles_template_patch(template: dict[str, Any], draft: VideoTemplateDraft) -> dict[str, Any]:
    current = to_record(template.get("particlesSettings"))
    return {
        "particlesSettings": {
            **current,
            "enabled": draft["particlesEnabled"],
            "maxCount": draft["particlesMaxCount"],
            "spawnRate": draft["particlesSpawnRate"],
            "lifetimeSec": draft["particlesLifetimeSec"],
            "speed": draft["particlesSpeed"],
            "reactivity": draft["particlesReactivity"],
            "audioMotionMode": draft["particlesAudioMotionMode"],
            "audioTravelBoost": draft["particlesAudioTravelBoost"],
            "smoothing": draft["particlesSmoothing"],
            "spawnMode": draft["particlesSpawnMode"],
            "spawnTrigger": draft["particlesSpawnTrigger"],
            "spawnThreshold": draft["particlesSpawnThreshold"],
            "variant": draft["particlesVariant"],
            "spawnArea": draft["particlesSpawnArea"],
            "travelMode": draft.get("particlesTravelMode", "spawnFlow"),
            "sizeJitter": draft["particlesSizeJitter"],
            "drift": draft["particlesDrift"],
            "swirl": draft["particlesSwirl"],
            "style": draft["particlesStyle"],
            "size": draft["particlesSize"],
            "opacity": draft["particlesOpacity"],
            "color": draft["particlesColor"],
            "reactColor": draft["particlesReactColor"],
            "colorMode": draft.get("particlesColorMode", "solid"),
            "paletteColors": list(draft.get("particlesPaletteColors") or []),
            "reactStrength": draft["particlesReactStrength"],
        }
    }


def build_text_template_patch(draft: VideoTemplateDraft) -> dict[str, Any]:
    # Freeform textOverlays UI was removed in favor of Album/Title domains.
    # Always clear the array on save so old animated layers cannot persist.
    _ = draft
    return {"textOverlays": []}


def build_album_template_patch(draft: VideoTemplateDraft) -> dict[str, Any]:
    from features.video.lib.text_domain_registry import album_settings_from_draft

    return {"albumText": album_settings_from_draft(draft)}


def build_title_template_patch(draft: VideoTemplateDraft) -> dict[str, Any]:
    from features.video.lib.text_domain_registry import title_settings_from_draft

    return {"titleText": title_settings_from_draft(draft)}


def build_video_workspace_template_save_patch(
    *,
    template: dict[str, Any],
    draft: VideoTemplateDraft,
    template_name: str,
    layers: list[dict[str, Any]],
) -> dict[str, Any]:
    effect_packs = draft.get("effectPacks") if isinstance(draft.get("effectPacks"), dict) else {}
    pack_entry = lambda domain: effect_packs.get(domain) if isinstance(effect_packs.get(domain), dict) else None
    return {
        "templateName": template_name.strip(),
        "effectPacks": {
            "spectrum": pack_entry("spectrum"),
            "background": pack_entry("background"),
            "logo": pack_entry("logo"),
            "particles": pack_entry("particles"),
            "album": pack_entry("album"),
            "title": pack_entry("title"),
        },
        **build_spectrum_template_patch(template, draft),
        **build_background_template_patch(template, draft),
        **build_atmosphere_template_patch(template, draft),
        **build_logo_template_patch(template, draft),
        **build_particles_template_patch(template, draft),
        **build_album_template_patch(draft),
        **build_title_template_patch(draft),
        **build_text_template_patch(draft),
        "layers": clone_layer_records(layers),
    }
