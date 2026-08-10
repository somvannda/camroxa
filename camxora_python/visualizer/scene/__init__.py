"""Composition Engine V1 — scene graph + fail-closed loader."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

COMPOSITION_SCHEMA_ID = "camxora.composition"
COMPOSITION_DOC_VERSION = 1
NONE = "none"

SCENE_OBJECTS: tuple[str, ...] = (
    "background",
    "spectrum",
    "logo",
    "text",
    "particles",
    "lighting",
    "camera",
    "audio",
    "overlay",
)


class CompositionContractError(ValueError):
    """Raised when a document is not a valid composition-engine scene."""


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, num))


def default_composition() -> dict[str, Any]:
    return {
        "version": COMPOSITION_DOC_VERSION,
        "colorPalette": None,
        "paletteIntensity": 1.0,
        "paletteSaturation": 1.0,
        "background": {
            "image": None,
            "motion": "static",
            "atmosphere": NONE,
            "brightness": 1.0,
            "contrast": 1.0,
            "reactivity": 0.0,
            "saturation": 1.0,
            "hue": 0.0,
            "smoothing": 0.8,
            "motionSpeed": 1.0,
            "motionAmplitude": 1.0,
            "motionZoom": 1.0,
            "motionWarp": 1.0,
            "atmosphereDensity": 1.0,
            "atmosphereSpeed": 1.0,
            "atmosphereOpacity": 1.0,
            "atmosphereWind": 1.0,
        },
        "spectrum": {
            "shape": NONE,
            "material": NONE,
            "animation": NONE,
            "barHeight": 1.0,
            "glow": 0.45,
            "opacity": 1.0,
            "blur": 0.0,
            "barWidthScale": 1.0,
            "thicknessScale": 1.0,
            "sizeScale": 1.0,
            "offsetX": 0.0,
            "offsetY": 0.0,
            "rotationDeg": 0.0,
            # Studio: Shape size (sizeScale) ≠ center-image Size px unless opted in.
            "fitRadiusToCenterImage": False,
            "colorPalette": None,
            "gradientColors": None,  # custom stops; None = use palette catalog
            "barCount": 64,
            "tipTaper": 0.0,
            "animationSpeed": 1.0,
            "animationScaleAmount": 1.0,
            "animationOpacityAmount": 1.0,
            "animationRotateAmount": 1.0,
            "animationAudioAmount": 1.0,
            "animationKick": 1.0,
            "animationSmoothing": None,
            "mirrored": None,  # None = inherit shape template
            "gravity": None,  # None = inherit shape template
            "peakCapsEnabled": False,
            "solidBand": False,
            "layers": [{"name": "Ring 1", "radiusOffset": 0.0, "opacity": 1.0, "enabled": True}],
            "selectedLayerIndex": 0,
        },
        "logo": {
            "enabled": True,
            "animation": NONE,
            "scale": 1.0,
            "opacity": 1.0,
            "circleMask": False,
            "fitToShape": True,
            "maskShape": "auto",
            # When True, Image size is clamped ≤ shape frame. When False, size may
            # exceed the frame (zoom) while Mask still crops to the shape silhouette.
            "containInShape": False,
            "reactivity": 0.0,
            "offsetX": 0.0,
            "offsetY": 0.0,
            "size": 192.0,
            # Image content rotation (independent of Spectrum Shape rotationDeg).
            "rotationDeg": 0.0,
        },
        "text": {"enabled": False, "opacity": 1.0, "scale": 1.0, "offsetY": 0.0},
        "overlay": {"enabled": False, "animation": NONE, "items": [], "amount": 0.28},
        "particles": {
            "type": NONE,
            "behavior": NONE,
            "spawn": 1.0,
            "size": 1.0,
            "opacity": 0.35,
            "speed": 1.0,
            "reactivity": 0.45,
        },
        "lighting": {
            "effect": NONE,
            "trigger": NONE,
            "intensity": 0.85,
            "thickness": 1.0,
            "glow": 0.55,
            "flashRate": 0.85,
            "speed": 1.0,
        },
        "camera": {
            "behavior": NONE,
            "zoomBias": 1.0,
            "panX": 0.0,
            "panY": 0.0,
            "shakeAmount": 0.5,
            "rollBias": 0.0,
        },
        "postProcessing": {"effects": [], "amount": 0.35},
        "audio": {"mapping": {}, "gain": 1.0, "smoothing": 0.65, "bassEmphasis": 1.0},
        "performance": {"quality": "medium", "lod": True},
    }


def default_assets() -> dict[str, Any]:
    return {
        "backgroundImage": None,
        "backgroundVideo": None,
        "logo": None,
        "audio": None,
        "audioTracks": [],
    }


def default_document() -> dict[str, Any]:
    return {
        "schema": COMPOSITION_SCHEMA_ID,
        "version": COMPOSITION_DOC_VERSION,
        "composition": default_composition(),
        "assets": default_assets(),
    }


def _nonempty(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def normalize_composition(raw: Any) -> dict[str, Any]:
    base = default_composition()
    if not isinstance(raw, dict):
        return base
    out = deepcopy(base)
    try:
        version = int(raw.get("version", COMPOSITION_DOC_VERSION))
    except (TypeError, ValueError):
        version = COMPOSITION_DOC_VERSION
    out["version"] = version if version > 0 else COMPOSITION_DOC_VERSION
    palette = raw.get("colorPalette")
    out["colorPalette"] = str(palette).strip() if palette not in (None, "") else None
    out["paletteIntensity"] = _clamp_float(raw.get("paletteIntensity"), 0.0, 2.0, 1.0)
    out["paletteSaturation"] = _clamp_float(raw.get("paletteSaturation"), 0.0, 2.0, 1.0)

    bg = raw.get("background") if isinstance(raw.get("background"), dict) else {}
    out["background"]["image"] = _optional(bg.get("image"))
    out["background"]["motion"] = _nonempty(bg.get("motion"), "static")
    out["background"]["atmosphere"] = _nonempty(bg.get("atmosphere"), NONE)
    out["background"]["brightness"] = _clamp_float(bg.get("brightness"), 0.2, 2.0, 1.0)
    out["background"]["contrast"] = _clamp_float(bg.get("contrast"), 0.2, 2.0, 1.0)
    out["background"]["reactivity"] = _clamp_float(bg.get("reactivity"), 0.0, 1.0, 0.0)
    out["background"]["saturation"] = _clamp_float(bg.get("saturation"), 0.0, 2.0, 1.0)
    out["background"]["hue"] = _clamp_float(bg.get("hue"), -180.0, 180.0, 0.0)
    out["background"]["smoothing"] = _clamp_float(bg.get("smoothing"), 0.0, 0.99, 0.8)
    out["background"]["motionSpeed"] = _clamp_float(bg.get("motionSpeed"), 0.15, 3.0, 1.0)
    out["background"]["motionAmplitude"] = _clamp_float(bg.get("motionAmplitude"), 0.15, 3.0, 1.0)
    out["background"]["motionZoom"] = _clamp_float(bg.get("motionZoom"), 0.15, 3.0, 1.0)
    out["background"]["motionWarp"] = _clamp_float(bg.get("motionWarp"), 0.0, 3.0, 1.0)
    out["background"]["atmosphereDensity"] = _clamp_float(bg.get("atmosphereDensity"), 0.0, 2.5, 1.0)
    out["background"]["atmosphereSpeed"] = _clamp_float(bg.get("atmosphereSpeed"), 0.1, 3.0, 1.0)
    out["background"]["atmosphereOpacity"] = _clamp_float(bg.get("atmosphereOpacity"), 0.0, 1.0, 1.0)
    out["background"]["atmosphereWind"] = _clamp_float(bg.get("atmosphereWind"), 0.0, 3.0, 1.0)

    spec = raw.get("spectrum") if isinstance(raw.get("spectrum"), dict) else {}
    out["spectrum"]["shape"] = _nonempty(spec.get("shape"), NONE)
    out["spectrum"]["material"] = _nonempty(spec.get("material"), NONE)
    out["spectrum"]["animation"] = _nonempty(spec.get("animation"), NONE)
    out["spectrum"]["barHeight"] = _clamp_float(spec.get("barHeight"), 0.25, 4.0, 1.0)
    out["spectrum"]["glow"] = _clamp_float(spec.get("glow"), 0.0, 1.0, 0.45)
    out["spectrum"]["opacity"] = _clamp_float(spec.get("opacity"), 0.1, 1.0, 1.0)
    out["spectrum"]["blur"] = _clamp_float(spec.get("blur"), 0.0, 8.0, 0.0)
    out["spectrum"]["barWidthScale"] = _clamp_float(spec.get("barWidthScale"), 0.08, 3.0, 1.0)
    out["spectrum"]["thicknessScale"] = _clamp_float(spec.get("thicknessScale"), 0.25, 3.0, 1.0)
    out["spectrum"]["sizeScale"] = _clamp_float(spec.get("sizeScale"), 0.35, 2.5, 1.0)
    out["spectrum"]["offsetX"] = _clamp_float(spec.get("offsetX"), -2.0, 2.0, 0.0)
    out["spectrum"]["offsetY"] = _clamp_float(spec.get("offsetY"), -2.0, 2.0, 0.0)
    try:
        rot = float(spec.get("rotationDeg") or 0.0) % 360.0
    except (TypeError, ValueError):
        rot = 0.0
    if rot < 0.0:
        rot += 360.0
    out["spectrum"]["rotationDeg"] = float(rot)
    out["spectrum"]["fitRadiusToCenterImage"] = bool(spec.get("fitRadiusToCenterImage", False))
    from visualizer.presets.palettes import normalize_color_palette_id
    from visualizer.scene.spectrum_layers import normalize_spectrum_layers

    out["spectrum"]["colorPalette"] = normalize_color_palette_id(spec.get("colorPalette"))
    raw_stops = spec.get("gradientColors")
    if isinstance(raw_stops, list) and len(raw_stops) >= 2:
        from features.video.lib.spectrum_color_engine import normalize_spectrum_gradient_colors

        out["spectrum"]["gradientColors"] = normalize_spectrum_gradient_colors(
            [str(c) for c in raw_stops],
            "#ff4fd8",
        )
    else:
        out["spectrum"]["gradientColors"] = None
    try:
        out["spectrum"]["barCount"] = int(round(max(24, min(160, float(spec.get("barCount") or 64)))))
    except (TypeError, ValueError):
        out["spectrum"]["barCount"] = 64
    out["spectrum"]["tipTaper"] = _clamp_float(spec.get("tipTaper"), 0.0, 1.0, 0.0)
    out["spectrum"]["animationSpeed"] = _clamp_float(spec.get("animationSpeed"), 0.15, 3.0, 1.0)
    out["spectrum"]["animationScaleAmount"] = _clamp_float(
        spec.get("animationScaleAmount"), 0.0, 2.5, 1.0
    )
    out["spectrum"]["animationOpacityAmount"] = _clamp_float(
        spec.get("animationOpacityAmount"), 0.0, 2.5, 1.0
    )
    out["spectrum"]["animationRotateAmount"] = _clamp_float(
        spec.get("animationRotateAmount"), 0.0, 2.5, 1.0
    )
    out["spectrum"]["animationAudioAmount"] = _clamp_float(
        spec.get("animationAudioAmount"), 0.0, 2.5, 1.0
    )
    out["spectrum"]["animationKick"] = _clamp_float(spec.get("animationKick"), 0.0, 2.5, 1.0)
    if spec.get("animationSmoothing") is None:
        out["spectrum"]["animationSmoothing"] = None
    else:
        out["spectrum"]["animationSmoothing"] = _clamp_float(
            spec.get("animationSmoothing"), 0.1, 1.0, 0.65
        )
    if spec.get("mirrored") is None:
        out["spectrum"]["mirrored"] = None
    else:
        out["spectrum"]["mirrored"] = bool(spec.get("mirrored"))
    from visualizer._spectrum_fast import normalize_spectrum_gravity

    raw_grav = spec.get("gravity")
    if raw_grav in (None, "", "none", "auto"):
        out["spectrum"]["gravity"] = None
    else:
        out["spectrum"]["gravity"] = normalize_spectrum_gravity(raw_grav)
    out["spectrum"]["peakCapsEnabled"] = bool(spec.get("peakCapsEnabled", False))
    out["spectrum"]["solidBand"] = bool(spec.get("solidBand", False))
    layers = normalize_spectrum_layers(spec.get("layers"), defaults=out["spectrum"])
    out["spectrum"]["layers"] = layers
    try:
        sel = int(spec.get("selectedLayerIndex") or 0)
    except (TypeError, ValueError):
        sel = 0
    out["spectrum"]["selectedLayerIndex"] = max(0, min(len(layers) - 1, sel))

    logo = raw.get("logo") if isinstance(raw.get("logo"), dict) else {}
    out["logo"]["enabled"] = bool(logo.get("enabled", True))
    out["logo"]["animation"] = _nonempty(logo.get("animation"), NONE)
    out["logo"]["scale"] = _clamp_float(logo.get("scale"), 0.25, 3.0, 1.0)
    out["logo"]["opacity"] = _clamp_float(logo.get("opacity"), 0.1, 1.0, 1.0)
    out["logo"]["circleMask"] = bool(logo.get("circleMask", False))
    if "fitToShape" in logo:
        out["logo"]["fitToShape"] = bool(logo.get("fitToShape"))
    else:
        # Default on: Vizzy-style clip to spectrum geometry.
        out["logo"]["fitToShape"] = True
    try:
        from visualizer.logo_mask import normalize_logo_mask_shape_id

        out["logo"]["maskShape"] = normalize_logo_mask_shape_id(logo.get("maskShape"))
    except Exception:
        out["logo"]["maskShape"] = "auto"
    if "containInShape" in logo:
        out["logo"]["containInShape"] = bool(logo.get("containInShape"))
    else:
        out["logo"]["containInShape"] = False
    out["logo"]["reactivity"] = _clamp_float(logo.get("reactivity"), 0.0, 1.0, 0.0)
    out["logo"]["offsetX"] = _clamp_float(logo.get("offsetX"), -0.5, 0.5, 0.0)
    out["logo"]["offsetY"] = _clamp_float(logo.get("offsetY"), -0.5, 0.5, 0.0)
    out["logo"]["size"] = _clamp_float(logo.get("size"), 64.0, 512.0, 192.0)
    try:
        rot = float(logo.get("rotationDeg") or 0.0) % 360.0
        if rot < 0.0:
            rot += 360.0
        out["logo"]["rotationDeg"] = float(rot)
    except (TypeError, ValueError):
        out["logo"]["rotationDeg"] = 0.0

    text = raw.get("text") if isinstance(raw.get("text"), dict) else {}
    out["text"]["enabled"] = bool(text.get("enabled", False))
    out["text"]["opacity"] = _clamp_float(text.get("opacity"), 0.1, 1.0, 1.0)
    out["text"]["scale"] = _clamp_float(text.get("scale"), 0.5, 2.5, 1.0)
    out["text"]["offsetY"] = _clamp_float(text.get("offsetY"), -0.4, 0.4, 0.0)

    overlay = raw.get("overlay") if isinstance(raw.get("overlay"), dict) else {}
    out["overlay"]["enabled"] = bool(overlay.get("enabled", False))
    out["overlay"]["animation"] = _nonempty(overlay.get("animation"), NONE)
    items = overlay.get("items")
    out["overlay"]["items"] = list(items) if isinstance(items, list) else []
    out["overlay"]["amount"] = _clamp_float(overlay.get("amount"), 0.05, 1.0, 0.28)

    particles = raw.get("particles") if isinstance(raw.get("particles"), dict) else {}
    out["particles"]["type"] = _nonempty(particles.get("type"), NONE)
    out["particles"]["behavior"] = _nonempty(particles.get("behavior"), NONE)
    out["particles"]["spawn"] = _clamp_float(particles.get("spawn"), 0.1, 3.0, 1.0)
    out["particles"]["size"] = _clamp_float(particles.get("size"), 0.25, 4.0, 1.0)
    out["particles"]["opacity"] = _clamp_float(particles.get("opacity"), 0.05, 1.0, 0.35)
    out["particles"]["speed"] = _clamp_float(particles.get("speed"), 0.25, 3.0, 1.0)
    out["particles"]["reactivity"] = _clamp_float(particles.get("reactivity"), 0.0, 1.0, 0.45)

    lighting = raw.get("lighting") if isinstance(raw.get("lighting"), dict) else {}
    out["lighting"]["effect"] = _nonempty(lighting.get("effect"), NONE)
    out["lighting"]["trigger"] = _nonempty(lighting.get("trigger"), NONE)
    out["lighting"]["intensity"] = _clamp_float(lighting.get("intensity"), 0.1, 1.5, 0.85)
    out["lighting"]["thickness"] = _clamp_float(lighting.get("thickness"), 0.5, 3.0, 1.0)
    out["lighting"]["glow"] = _clamp_float(lighting.get("glow"), 0.0, 1.0, 0.55)
    out["lighting"]["flashRate"] = _clamp_float(lighting.get("flashRate"), 0.1, 2.0, 0.85)
    out["lighting"]["speed"] = _clamp_float(lighting.get("speed"), 0.25, 3.0, 1.0)

    camera = raw.get("camera") if isinstance(raw.get("camera"), dict) else {}
    out["camera"]["behavior"] = _nonempty(camera.get("behavior"), NONE)
    out["camera"]["zoomBias"] = _clamp_float(camera.get("zoomBias"), 0.7, 1.6, 1.0)
    out["camera"]["panX"] = _clamp_float(camera.get("panX"), -0.5, 0.5, 0.0)
    out["camera"]["panY"] = _clamp_float(camera.get("panY"), -0.5, 0.5, 0.0)
    out["camera"]["shakeAmount"] = _clamp_float(camera.get("shakeAmount"), 0.0, 1.0, 0.5)
    out["camera"]["rollBias"] = _clamp_float(camera.get("rollBias"), -15.0, 15.0, 0.0)

    post = raw.get("postProcessing") if isinstance(raw.get("postProcessing"), dict) else {}
    effects = post.get("effects")
    out["postProcessing"]["effects"] = (
        [str(x).strip() for x in effects if str(x).strip()] if isinstance(effects, list) else []
    )
    out["postProcessing"]["amount"] = _clamp_float(post.get("amount"), 0.05, 1.0, 0.35)

    audio = raw.get("audio") if isinstance(raw.get("audio"), dict) else {}
    mapping = audio.get("mapping")
    try:
        from visualizer.composition_effects.audio_mapping import normalize_audio_mapping

        out["audio"]["mapping"] = normalize_audio_mapping(mapping)
    except Exception:
        out["audio"]["mapping"] = dict(mapping) if isinstance(mapping, dict) else {}
    out["audio"]["gain"] = _clamp_float(audio.get("gain"), 0.25, 3.0, 1.0)
    out["audio"]["smoothing"] = _clamp_float(audio.get("smoothing"), 0.0, 0.99, 0.65)
    out["audio"]["bassEmphasis"] = _clamp_float(audio.get("bassEmphasis"), 0.5, 2.0, 1.0)

    perf = raw.get("performance") if isinstance(raw.get("performance"), dict) else {}
    quality = str(perf.get("quality") or "medium").strip().lower()
    out["performance"]["quality"] = quality if quality in {"low", "medium", "high"} else "medium"
    out["performance"]["lod"] = bool(perf.get("lod", True))

    # Normalize catalog ids when present (keep unknown as-is for forward compat).
    try:
        from visualizer.presets.atmosphere import normalize_atmosphere_id
        from visualizer.presets.background_motion import normalize_background_motion_id
        from visualizer.presets.camera import normalize_camera_behavior_id
        from visualizer.presets.lighting import (
            normalize_lighting_effect_id,
            normalize_lighting_trigger_id,
        )
        from visualizer.presets.post import normalize_post_effects_list

        motion = normalize_background_motion_id(out["background"]["motion"])
        if motion:
            out["background"]["motion"] = motion
        atm = normalize_atmosphere_id(out["background"]["atmosphere"])
        out["background"]["atmosphere"] = atm or NONE
        le = normalize_lighting_effect_id(out["lighting"]["effect"])
        out["lighting"]["effect"] = le or NONE
        lt = normalize_lighting_trigger_id(out["lighting"]["trigger"])
        out["lighting"]["trigger"] = lt or NONE
        cam = normalize_camera_behavior_id(out["camera"]["behavior"])
        out["camera"]["behavior"] = cam or NONE
        out["postProcessing"]["effects"] = normalize_post_effects_list(
            out["postProcessing"]["effects"]
        )
    except Exception:
        pass
    return out


def normalize_assets(raw: Any) -> dict[str, Any]:
    base = default_assets()
    if not isinstance(raw, dict):
        return base
    out = dict(base)
    for key in ("backgroundImage", "backgroundVideo", "logo", "audio"):
        out[key] = _optional(raw.get(key))
    tracks_raw = raw.get("audioTracks")
    tracks: list[str] = []
    if isinstance(tracks_raw, list):
        for item in tracks_raw:
            path = _optional(item)
            if path and path not in tracks:
                tracks.append(path)
    active = out.get("audio")
    if active and active not in tracks:
        tracks.insert(0, str(active))
    out["audioTracks"] = tracks
    return out


def _optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass
class Scene:
    """In-memory composition scene (architecture tree)."""

    schema: str = COMPOSITION_SCHEMA_ID
    version: int = COMPOSITION_DOC_VERSION
    composition: dict[str, Any] = field(default_factory=default_composition)
    assets: dict[str, Any] = field(default_factory=default_assets)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "composition": deepcopy(self.composition),
            "assets": deepcopy(self.assets),
        }


def load_scene(doc: Any) -> Scene:
    """Fail-closed loader: composition is required; legacy-only docs are rejected."""
    if not isinstance(doc, dict):
        raise CompositionContractError("scene document must be a dict")

    # Hard cut: refuse documents that only have legacy authority fields.
    has_composition = isinstance(doc.get("composition"), dict) and bool(doc.get("composition"))
    if not has_composition:
        raise CompositionContractError(
            "missing composition — engine v1 requires schema camxora.composition "
            "(legacy style/particlesSettings-only templates are not supported)"
        )

    schema = str(doc.get("schema") or COMPOSITION_SCHEMA_ID).strip() or COMPOSITION_SCHEMA_ID
    if schema not in (COMPOSITION_SCHEMA_ID, "camxora.composition.v1"):
        # Allow missing schema when composition is present (in-memory drafts),
        # but reject explicit foreign schemas.
        if "schema" in doc and schema:
            raise CompositionContractError(f"unsupported scene schema: {schema!r}")

    try:
        version = int(doc.get("version", COMPOSITION_DOC_VERSION))
    except (TypeError, ValueError) as exc:
        raise CompositionContractError("invalid document version") from exc

    composition = normalize_composition(doc.get("composition"))
    assets = normalize_assets(doc.get("assets"))

    # Prefer composition.background.image when assets.backgroundImage empty.
    if not assets.get("backgroundImage") and composition["background"].get("image"):
        assets["backgroundImage"] = composition["background"]["image"]

    return Scene(schema=COMPOSITION_SCHEMA_ID, version=max(1, version), composition=composition, assets=assets)


def require_composition_document(doc: Any) -> dict[str, Any]:
    """Validate and return a normalized composition document."""
    scene = load_scene(doc)
    return scene.to_document()


__all__ = (
    "COMPOSITION_DOC_VERSION",
    "COMPOSITION_SCHEMA_ID",
    "CompositionContractError",
    "NONE",
    "SCENE_OBJECTS",
    "Scene",
    "default_assets",
    "default_composition",
    "default_document",
    "load_scene",
    "normalize_assets",
    "normalize_composition",
    "require_composition_document",
)
