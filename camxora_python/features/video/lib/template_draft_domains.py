"""Draft domain dirty tracking — port of Electron templateDraftDomains."""

from __future__ import annotations

import json
from typing import Any

DOMAIN_KEYS = (
    "palette",
    "background",
    "spectrum",
    "logo",
    "text",
    "overlay",
    "particles",
    "lighting",
    "camera",
    "post",
    "audio_mapping",
    "album",
    "title",
    "lightning",  # legacy alias
)


def _pick_spectrum_slice(draft: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "spectrumEnabled",
        "style",
        "audioInputGain",
        "audioBarHeight",
        "audioBandContrast",
        "audioTransientFocus",
        "audioKickImpact",
        "audioBassEmphasis",
        "audioTrebleShimmer",
        "audioPeakHoldBlend",
        "audioMotionSmoothing",
        "flyingGlowWingMotionSpeed",
        "flyingGlowWingRelease",
        "spectrumAttachToLogo",
        "spectrumLogoGap",
        "anchor",
        "positionX",
        "positionY",
    )
    return {key: draft.get(key) for key in keys}


def _pick_background_slice(draft: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "backgroundEnabled",
        "backgroundPath",
        "backgroundFitMode",
        "backgroundUserScale",
        "backgroundBrightness",
        "backgroundContrast",
        "backgroundSaturation",
        "backgroundHue",
        "backgroundReactivity",
        "backgroundSmoothing",
        "backgroundMotionMode",
        "backgroundMotionZoomStrength",
        "backgroundMotionVibrateStrength",
        "backgroundMotionSpeed",
        "vignetteEnabled",
        "vignetteStrength",
        "vignetteFeather",
        "vignetteOpacity",
        "vignetteColor",
        "vignetteReactivity",
        "smokeEnabled",
        "smokeStrength",
        "smokeBlur",
        "smokeNoise",
        "smokeSpeed",
        "smokeOpacity",
        "smokeColor",
    )
    return {key: draft.get(key) for key in keys}


def _pick_logo_slice(draft: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "logoEnabled",
        "logoSpinEnabled",
        "logoSpinDirection",
        "logoSpinSpeed",
        "logoPath",
        "logoShape",
        "logoSizeStep",
        "logoOpacity",
        "logoReactivity",
        "logoSmoothing",
        "logoMotionMode",
        "logoMotionZoomStrength",
        "logoMotionVibrateStrength",
        "logoMotionSpeed",
        "logoPositionX",
        "logoPositionY",
        "spectrumAttachToLogo",
        "spectrumLogoGap",
    )
    return {key: draft.get(key) for key in keys}


def _pick_particles_slice(draft: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "particlesEnabled",
        "particlesMaxCount",
        "particlesSpawnRate",
        "particlesLifetimeSec",
        "particlesSpeed",
        "particlesReactivity",
        "particlesAudioTravelBoost",
        "particlesAudioMotionMode",
        "particlesSmoothing",
        "particlesSpawnMode",
        "particlesSpawnTrigger",
        "particlesSpawnThreshold",
        "particlesVariant",
        "particlesSpawnArea",
        "particlesTravelMode",
        "particlesSizeJitter",
        "particlesDrift",
        "particlesSwirl",
        "particlesStyle",
        "particlesGlow",
        "particlesSize",
        "particlesOpacity",
        "particlesColor",
        "particlesReactColor",
        "particlesColorMode",
        "particlesPaletteColors",
        "particlesReactStrength",
        "particlesTrailEnabled",
        "particlesTrailLength",
        "particlesTrailFade",
        "particlesTrailWidth",
    )
    return {key: draft.get(key) for key in keys}


def _pick_text_slice(draft: dict[str, Any]) -> dict[str, Any]:
    overlays = draft.get("textOverlays")
    return {"textOverlays": overlays if isinstance(overlays, list) else []}


def _pick_album_slice(draft: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "albumEnabled",
        "albumContentMode",
        "albumManualText",
        "albumStylePreset",
        "albumFontFamily",
        "albumFontSize",
        "albumBold",
        "albumItalic",
        "albumColor",
        "albumFillMode",
        "albumGradientColors",
        "albumGradientDirection",
        "albumGlowColor",
        "albumGlowMode",
        "albumGlowGradientColors",
        "albumGlowGradientDirection",
        "albumStrokeColor",
        "albumStrokeWidth",
        "albumShadow",
        "albumShadowBlur",
        "albumGlow",
        "albumGlowBlur",
        "albumExtrudeDepth",
        "albumExtrudeColor",
        "albumLetterSpacing",
        "albumLineSpacing",
        "albumBoxWidth",
        "albumAlign",
        "albumAnchor",
        "albumX",
        "albumY",
        "albumOpacity",
    )
    return {key: draft.get(key) for key in keys}


def _pick_title_slice(draft: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "titleEnabled",
        "titleContentMode",
        "titleListStyle",
        "titleNumberIndent",
        "titleLayout",
        "titleManualTitles",
        "titleListColor",
        "titleListActiveColor",
        "titleListActiveIndex",
        "titleShowDurations",
        "titleNowPlayingEnabled",
        "titleNowPlayingPill",
        "titleTrackCountBadge",
        "titleTracklistHeader",
        "titleActiveRowPlate",
        "titlePlaylistLook",
        "titlePanelOpacity",
        "titlePanelFrost",
        "titlePanelBorderWidth",
        "titlePanelBorderColor",
        "titlePanelSpecular",
        "titlePanelFill",
        "titleStylePreset",
        "titleFontFamily",
        "titleFontSize",
        "titleBold",
        "titleItalic",
        "titleColor",
        "titleFillMode",
        "titleGradientColors",
        "titleGradientDirection",
        "titleGlowColor",
        "titleGlowMode",
        "titleGlowGradientColors",
        "titleGlowGradientDirection",
        "titleStrokeColor",
        "titleStrokeWidth",
        "titleShadow",
        "titleShadowBlur",
        "titleGlow",
        "titleGlowBlur",
        "titleExtrudeDepth",
        "titleExtrudeColor",
        "titleLetterSpacing",
        "titleLineSpacing",
        "titleBoxWidth",
        "titleAlign",
        "titleAnchor",
        "titleX",
        "titleY",
        "titleOpacity",
    )
    return {key: draft.get(key) for key in keys}


def pick_album_draft_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_album_slice(draft)


def pick_title_draft_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_title_slice(draft)


def pick_spectrum_draft_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_spectrum_slice(draft)


def pick_background_draft_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_background_slice(draft)


def pick_logo_draft_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_logo_slice(draft)


def pick_particles_draft_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_particles_slice(draft)


def _pick_composition_keys(draft: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: draft.get(key) for key in keys}


def _pick_lighting_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_composition_keys(
        draft,
        ("compositionLightingEffect", "compositionLightingTrigger", "lightningEnabled"),
    )


def pick_lightning_draft_slice(draft: dict[str, Any]) -> dict[str, Any]:
    return _pick_lighting_slice(draft)


def build_draft_dirty_state(
    draft: dict[str, Any] | None,
    persisted: dict[str, Any] | None,
    *,
    spectrum_dirty: bool = False,
    lightning_dirty: bool = False,
) -> dict[str, bool]:
    if not draft or not persisted:
        return {domain: False for domain in DOMAIN_KEYS}

    def changed(local_slice: dict[str, Any], persisted_slice: dict[str, Any]) -> bool:
        return json.dumps(local_slice, sort_keys=True) != json.dumps(persisted_slice, sort_keys=True)

    lighting_dirty_flag = lightning_dirty or changed(
        _pick_lighting_slice(draft), _pick_lighting_slice(persisted)
    )
    return {
        "palette": changed(
            _pick_composition_keys(draft, ("compositionColorPalette",)),
            _pick_composition_keys(persisted, ("compositionColorPalette",)),
        ),
        "spectrum": spectrum_dirty
        or changed(_pick_spectrum_slice(draft), _pick_spectrum_slice(persisted))
        or changed(
            _pick_composition_keys(
                draft,
                (
                    "compositionSpectrumShape",
                    "compositionSpectrumMaterial",
                    "compositionSpectrumAnimation",
                ),
            ),
            _pick_composition_keys(
                persisted,
                (
                    "compositionSpectrumShape",
                    "compositionSpectrumMaterial",
                    "compositionSpectrumAnimation",
                ),
            ),
        ),
        "background": changed(_pick_background_slice(draft), _pick_background_slice(persisted))
        or changed(
            _pick_composition_keys(
                draft, ("compositionBackgroundMotion", "compositionBackgroundAtmosphere")
            ),
            _pick_composition_keys(
                persisted, ("compositionBackgroundMotion", "compositionBackgroundAtmosphere")
            ),
        ),
        "logo": changed(_pick_logo_slice(draft), _pick_logo_slice(persisted))
        or changed(
            _pick_composition_keys(draft, ("compositionLogoAnimation",)),
            _pick_composition_keys(persisted, ("compositionLogoAnimation",)),
        ),
        "particles": changed(_pick_particles_slice(draft), _pick_particles_slice(persisted))
        or changed(
            _pick_composition_keys(
                draft, ("compositionParticleType", "compositionParticleBehavior")
            ),
            _pick_composition_keys(
                persisted, ("compositionParticleType", "compositionParticleBehavior")
            ),
        ),
        "lighting": lighting_dirty_flag,
        "lightning": lighting_dirty_flag,
        "camera": changed(
            _pick_composition_keys(draft, ("compositionCameraBehavior",)),
            _pick_composition_keys(persisted, ("compositionCameraBehavior",)),
        ),
        "post": changed(
            _pick_composition_keys(draft, ("compositionPostEffects",)),
            _pick_composition_keys(persisted, ("compositionPostEffects",)),
        ),
        "audio_mapping": changed(
            _pick_composition_keys(draft, ("compositionAudioMapping",)),
            _pick_composition_keys(persisted, ("compositionAudioMapping",)),
        ),
        "overlay": changed(
            _pick_composition_keys(
                draft, ("compositionOverlayEnabled", "compositionOverlayAnimation")
            ),
            _pick_composition_keys(
                persisted, ("compositionOverlayEnabled", "compositionOverlayAnimation")
            ),
        ),
        "album": changed(_pick_album_slice(draft), _pick_album_slice(persisted)),
        "title": changed(_pick_title_slice(draft), _pick_title_slice(persisted)),
        "text": changed(_pick_text_slice(draft), _pick_text_slice(persisted))
        or changed(
            _pick_composition_keys(draft, ("compositionTextEnabled",)),
            _pick_composition_keys(persisted, ("compositionTextEnabled",)),
        ),
    }
