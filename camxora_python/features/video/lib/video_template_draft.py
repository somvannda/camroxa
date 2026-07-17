"""Video template draft builders — port of Electron domain *Settings.ts files."""

from __future__ import annotations

import copy
import json
from typing import Any

from features.video.lib.particle_color_engine import normalize_particle_palette_colors
from features.video.lib.template_value_utils import (
    normalize_color,
    to_boolean,
    to_number,
    to_record,
    to_string_value,
)

VideoTemplateDraft = dict[str, Any]


def normalize_spectrum_preset_key(style_key: str) -> str:
    """Normalize style ids to Camxora-native keys (legacy pack ids alias in)."""
    normalized = str(style_key or "").strip().lower()
    if not normalized:
        return "orbit-spikes"
    aliases = {
        # Camxora native
        "orbit-spikes": "orbit-spikes",
        "signal-needles": "signal-needles",
        "pulse-beads": "pulse-beads",
        "mirror-blades": "mirror-blades",
        "aurora-ribbon": "aurora-ribbon",
        "magma-ridge": "magma-ridge",
        "plasma-bloom": "plasma-bloom",
        "grid-steps": "grid-steps",
        "ignition-flare": "ignition-flare",
        "drift-capsules": "drift-capsules",
        # Legacy → Camxora
        "classic-vertical": "orbit-spikes",
        "straight-bars": "orbit-spikes",
        "thin-lines": "signal-needles",
        "dot-matrix": "pulse-beads",
        "symmetrical": "mirror-blades",
        "symmetrical-bars": "mirror-blades",
        "orbital-bars": "mirror-blades",
        "soft-waveform": "aurora-ribbon",
        "continuous-waveform": "aurora-ribbon",
        "wave-ribbon": "aurora-ribbon",
        "mountain": "magma-ridge",
        "liquid": "plasma-bloom",
        "liquid-mass": "plasma-bloom",
        "pixel-bars": "grid-steps",
        "neon-pulse": "ignition-flare",
        "flying-glow": "ignition-flare",
        "halo-stack": "ignition-flare",
        "floating-blocks": "drift-capsules",
    }
    return aliases.get(normalized, normalized)


def get_recommended_spectrum_logo_gap(logo_shape: str, logo_size_step: float) -> float:
    normalized_shape = str(logo_shape or "").strip().lower()
    safe_size_step = max(1.0, min(10.0, logo_size_step or 1.0))
    base_gap = 18.0 if normalized_shape == "circle" else 28.0
    size_bias = safe_size_step * 1.6 if normalized_shape == "circle" else safe_size_step * 2.6
    return round(base_gap + size_bias, 1)


def _logo_real_size_to_slider_value(real_size: float) -> float:
    return max(1.0, min(10.0, round(real_size / 100.0, 2)))


def read_template_effect_pack_map(template: dict[str, Any]) -> dict[str, dict[str, str]]:
    effect_packs = to_record(template.get("effectPacks"))
    result: dict[str, dict[str, str]] = {}
    for domain in ("spectrum", "background", "logo", "particles", "album", "title"):
        entry = effect_packs.get(domain)
        if not isinstance(entry, dict):
            continue
        pack_id = str(entry.get("packId", "")).strip()
        version = str(entry.get("version", "")).strip()
        if pack_id and version:
            result[domain] = {"packId": pack_id, "version": version}
    return result


def build_default_text_overlay_draft() -> dict[str, Any]:
    return {
        "enabled": False,
        "text": "",
        "startSec": 0,
        "durationSec": 3,
        "anchor": "center",
        "x": 24,
        "y": 24,
        "fontSize": 46,
        "color": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 2,
        "shadow": 0.4,
        "animation": "fade",
    }


def build_logo_settings_state(template: dict[str, Any], logo_path: str) -> dict[str, Any]:
    logo_settings = to_record(template.get("logoSettings"))
    logo_shape = "circle" if to_boolean(logo_settings.get("circleMask"), True) else "square"
    return {
        "logoEnabled": to_boolean(logo_settings.get("enabled"), True),
        "logoSpinEnabled": to_boolean(logo_settings.get("spinEnabled"), False),
        "logoSpinDirection": to_string_value(logo_settings.get("spinDirection"), "cw"),
        "logoSpinSpeed": to_number(logo_settings.get("spinSpeed"), 0),
        "logoPath": to_string_value(logo_path, to_string_value(template.get("logoPath"), "")),
        "logoShape": logo_shape,
        "logoSizeStep": _logo_real_size_to_slider_value(to_number(logo_settings.get("size"), 200)),
        "logoOpacity": to_number(logo_settings.get("opacity"), 1),
        "logoReactivity": to_number(logo_settings.get("reactivity"), 0),
        "logoSmoothing": to_number(logo_settings.get("smoothing"), 0.75),
        "logoMotionMode": to_string_value(logo_settings.get("motionMode"), "none"),
        "logoMotionZoomStrength": to_number(logo_settings.get("motionZoomStrength"), 1),
        "logoMotionVibrateStrength": to_number(logo_settings.get("motionVibrateStrength"), 1),
        "logoMotionSpeed": to_number(logo_settings.get("motionSpeed"), 1),
    }


def build_spectrum_settings_state(
    template: dict[str, Any],
    logo_shape: str,
    logo_size_step: float,
) -> dict[str, Any]:
    audio_settings = to_record(template.get("audioSettings"))
    position = to_record(template.get("position"))
    preview_bindings = to_record(template.get("previewBindings"))
    return {
        "spectrumEnabled": to_boolean(template.get("spectrumEnabled"), True),
        "style": normalize_spectrum_preset_key(to_string_value(template.get("style"), "orbit-spikes")),
        "audioInputGain": to_number(
            audio_settings.get("inputGain"),
            to_number(audio_settings.get("sensitivity"), 1),
        ),
        "audioBarHeight": to_number(audio_settings.get("barHeight"), 1),
        "audioBandContrast": to_number(
            audio_settings.get("bandContrast"),
            to_number(audio_settings.get("heightBoost"), 1),
        ),
        "audioTransientFocus": to_number(audio_settings.get("transientFocus"), 1),
        "audioKickImpact": to_number(
            audio_settings.get("kickImpact"),
            to_number(audio_settings.get("kickDrop"), 0),
        ),
        "audioBassEmphasis": to_number(audio_settings.get("bassEmphasis"), 1),
        "audioTrebleShimmer": to_number(audio_settings.get("trebleShimmer"), 1),
        "audioPeakHoldBlend": to_number(audio_settings.get("peakHoldBlend"), 0),
        "audioMotionSmoothing": to_number(
            audio_settings.get("motionSmoothing"),
            to_number(audio_settings.get("smoothing"), 0.8),
        ),
        "flyingGlowWingMotionSpeed": to_number(
            audio_settings.get("flyingGlowWingMotionSpeed"),
            to_number(audio_settings.get("wingMotionSpeed"), 1),
        ),
        "flyingGlowWingRelease": to_number(
            audio_settings.get("flyingGlowWingRelease"),
            to_number(audio_settings.get("wingRelease"), 0.9),
        ),
        "spectrumAttachToLogo": to_boolean(preview_bindings.get("spectrumAttachToLogo"), False),
        "spectrumLogoGap": to_number(
            preview_bindings.get("spectrumLogoGap"),
            get_recommended_spectrum_logo_gap(logo_shape, logo_size_step),
        ),
        "anchor": to_string_value(position.get("anchor"), "center"),
        "positionX": to_number(position.get("x"), 0),
        "positionY": to_number(position.get("y"), 0),
    }


def build_background_settings_state(template: dict[str, Any]) -> dict[str, Any]:
    background_settings = to_record(template.get("backgroundSettings"))
    return {
        "backgroundEnabled": to_boolean(background_settings.get("enabled"), True),
        "backgroundFitMode": to_string_value(background_settings.get("fitMode"), "cover"),
        "backgroundUserScale": to_number(background_settings.get("userScale"), 1),
        "backgroundBrightness": to_number(background_settings.get("brightness"), 1),
        "backgroundContrast": to_number(background_settings.get("contrast"), 1),
        "backgroundSaturation": to_number(background_settings.get("saturation"), 1),
        "backgroundHue": to_number(background_settings.get("hue"), 0),
        "backgroundReactivity": to_number(background_settings.get("reactivity"), 0),
        "backgroundSmoothing": to_number(background_settings.get("smoothing"), 0.8),
        "backgroundMotionMode": to_string_value(background_settings.get("motionMode"), "none"),
        "backgroundMotionZoomStrength": to_number(background_settings.get("motionZoomStrength"), 1),
        "backgroundMotionVibrateStrength": to_number(background_settings.get("motionVibrateStrength"), 1),
        "backgroundMotionSpeed": to_number(background_settings.get("motionSpeed"), 1),
    }


def build_atmosphere_settings_state(template: dict[str, Any]) -> dict[str, Any]:
    effects = to_record(template.get("effects"))
    vignette = to_record(effects.get("vignette"))
    smoke = to_record(effects.get("smoke"))
    return {
        "vignetteEnabled": to_boolean(vignette.get("enabled"), False),
        "vignetteStrength": to_number(vignette.get("strength"), 0.35),
        "vignetteFeather": to_number(vignette.get("feather"), 0.65),
        "vignetteOpacity": to_number(vignette.get("opacity"), 0.65),
        "vignetteColor": normalize_color(vignette.get("color"), "#000000"),
        "smokeEnabled": to_boolean(smoke.get("enabled"), False),
        "smokeStrength": to_number(smoke.get("strength"), 0.35),
        "smokeBlur": to_number(smoke.get("blur"), 0.55),
        "smokeNoise": to_number(smoke.get("noise"), 0.55),
        "smokeSpeed": to_number(smoke.get("speed"), 0.35),
        "smokeOpacity": to_number(smoke.get("opacity"), 0.55),
        "smokeColor": normalize_color(smoke.get("color"), "#000000"),
    }


def build_particle_settings_state(template: dict[str, Any]) -> dict[str, Any]:
    particles_settings = to_record(template.get("particlesSettings"))
    base_color = normalize_color(particles_settings.get("color"), "#ffffff")
    palette_raw = particles_settings.get("paletteColors")
    color_mode = (
        "palette"
        if to_string_value(particles_settings.get("colorMode"), "solid").lower() == "palette"
        else "solid"
    )
    palette_colors = (
        normalize_particle_palette_colors(
            list(palette_raw),
            base_color,
            require_stops=(color_mode == "palette"),
        )
        if isinstance(palette_raw, list)
        else []
    )
    return {
        "particlesEnabled": to_boolean(particles_settings.get("enabled"), True),
        "particlesMaxCount": int(to_number(particles_settings.get("maxCount"), 200)),
        "particlesSpawnRate": to_number(particles_settings.get("spawnRate"), 100),
        "particlesLifetimeSec": to_number(particles_settings.get("lifetimeSec"), 1.6),
        "particlesSpeed": to_number(particles_settings.get("speed"), 1),
        "particlesReactivity": to_number(particles_settings.get("reactivity"), 0.1),
        "particlesAudioTravelBoost": to_number(particles_settings.get("audioTravelBoost"), 1),
        "particlesAudioMotionMode": to_string_value(particles_settings.get("audioMotionMode"), "both"),
        "particlesSmoothing": to_number(particles_settings.get("smoothing"), 0.65),
        "particlesSpawnMode": to_string_value(particles_settings.get("spawnMode"), "always"),
        "particlesSpawnTrigger": to_string_value(particles_settings.get("spawnTrigger"), "both"),
        "particlesSpawnThreshold": to_number(particles_settings.get("spawnThreshold"), 0.15),
        "particlesVariant": to_string_value(particles_settings.get("variant"), "classic"),
        "particlesSpawnArea": to_string_value(particles_settings.get("spawnArea"), "centerRing"),
        "particlesTravelMode": to_string_value(particles_settings.get("travelMode"), "spawnFlow"),
        "particlesSizeJitter": to_number(particles_settings.get("sizeJitter"), 0),
        "particlesDrift": to_number(particles_settings.get("drift"), 0),
        "particlesSwirl": to_number(particles_settings.get("swirl"), 0),
        "particlesStyle": to_string_value(particles_settings.get("style"), "dot"),
        "particlesSize": to_number(particles_settings.get("size"), 2),
        "particlesOpacity": to_number(particles_settings.get("opacity"), 0.35),
        "particlesColor": base_color,
        "particlesReactColor": normalize_color(particles_settings.get("reactColor"), "#ffffff"),
        "particlesColorMode": color_mode,
        "particlesPaletteColors": palette_colors,
        "particlesReactStrength": to_number(particles_settings.get("reactStrength"), 0.65),
    }


def build_text_settings_state(template: dict[str, Any]) -> dict[str, Any]:
    # Freeform textOverlays UI was removed; Album/Title domains own on-screen text.
    # Drop any persisted legacy layers so they cannot animate in preview.
    _ = template
    return {"textOverlays": []}


def build_video_template_draft(template: dict[str, Any], *, logo_path: str) -> VideoTemplateDraft:
    logo_state = build_logo_settings_state(template, logo_path)
    draft: VideoTemplateDraft = {}
    draft.update(
        build_spectrum_settings_state(
            template,
            str(logo_state["logoShape"]),
            float(logo_state["logoSizeStep"]),
        )
    )
    draft.update(build_background_settings_state(template))
    draft.update(build_atmosphere_settings_state(template))
    draft.update(logo_state)
    draft.update(build_particle_settings_state(template))
    draft.update(build_text_settings_state(template))
    from features.video.lib.text_domain_registry import (
        build_album_settings_state,
        build_title_settings_state,
    )

    draft.update(build_album_settings_state(template))
    draft.update(build_title_settings_state(template))
    draft["effectPacks"] = read_template_effect_pack_map(template)
    return draft


def clone_layer_records(layers: Any) -> list[dict[str, Any]]:
    if not isinstance(layers, list):
        return []
    return [copy.deepcopy(item) for item in layers if isinstance(item, dict)]


def draft_snapshot(draft: VideoTemplateDraft | None) -> str:
    if not draft:
        return ""
    return json.dumps(draft, sort_keys=True, separators=(",", ":"))
