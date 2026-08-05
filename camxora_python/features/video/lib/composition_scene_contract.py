"""Composition Engine P0/P1 — scene contract (architecture tree JSON).

Frozen authoring-layer keys live under template ``composition`` (version 1).
The GPU renderer continues to read legacy fields
(``backgroundSettings``, ``style``, ``particlesSettings``, ``effects``, …).

P0: typed stubs + legacy projection.
P1: orthogonal axis apply (see ``composition_axes.py``); preserve material /
animation / behavior across legacy re-projection.

Do not invent conflicting key names outside this module /
``docs/COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

COMPOSITION_SCHEMA_VERSION = 1

# Layer 1 — scene objects (never change)
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

# Text = typography domains. Overlay = top composites (frames/stickers/watermarks).
TEXT_LEGACY_KEYS: tuple[str, ...] = ("albumText", "titleText", "textOverlays")
OVERLAY_LEGACY_KEYS: tuple[str, ...] = ("overlaySettings",)

# Architecture-tree stub enums (full catalogs land in later phases)
NONE = "none"

BACKGROUND_MOTION_CANONICAL: tuple[str, ...] = (
    "static",
    "slow_zoom",
    "ken_burns",
    "orbit",
    "parallax",
    "ripple",
    "energy_wave",
    "floating",
    "rotate",
    "warp",
)

# Legacy backgroundSettings.motionMode → composition.background.motion
_LEGACY_BG_MOTION_TO_COMPOSITION: dict[str, str] = {
    "none": "static",
    "zoom": "slow_zoom",
    "vibrate": "vibrate",  # retained until P9 expands motion library
}

_COMPOSITION_BG_MOTION_TO_LEGACY: dict[str, str] = {
    "static": "none",
    "slow_zoom": "zoom",
    "vibrate": "vibrate",
    "none": "none",
    "zoom": "zoom",
}


def default_composition_scene() -> dict[str, Any]:
    """Empty / stub architecture tree. Safe defaults; GPU still uses legacy fields."""
    return {
        "version": COMPOSITION_SCHEMA_VERSION,
        "colorPalette": None,
        "background": {
            "image": None,
            "motion": "static",
            "atmosphere": NONE,
        },
        "spectrum": {
            "shape": NONE,
            "material": NONE,
            "animation": NONE,
        },
        "logo": {
            "enabled": True,
            "animation": NONE,
        },
        "text": {
            "enabled": False,
        },
        "overlay": {
            "enabled": False,
            "animation": NONE,
            "items": [],
        },
        "particles": {
            "type": NONE,
            "behavior": NONE,
        },
        "lighting": {
            "effect": NONE,
            "trigger": NONE,
        },
        "camera": {
            "behavior": NONE,
        },
        "postProcessing": {
            "effects": [],
        },
        "audio": {
            "mapping": {},
        },
    }


def normalize_composition_scene(raw: Any) -> dict[str, Any]:
    """Clamp unknown shapes to defaults; preserve known stub values."""
    base = default_composition_scene()
    if not isinstance(raw, dict):
        return base

    out = deepcopy(base)
    try:
        version = int(raw.get("version", COMPOSITION_SCHEMA_VERSION))
    except (TypeError, ValueError):
        version = COMPOSITION_SCHEMA_VERSION
    out["version"] = version if version > 0 else COMPOSITION_SCHEMA_VERSION

    palette = raw.get("colorPalette")
    out["colorPalette"] = str(palette).strip() if palette not in (None, "") else None

    bg = raw.get("background") if isinstance(raw.get("background"), dict) else {}
    out["background"]["image"] = _optional_str(bg.get("image"))
    out["background"]["motion"] = _nonempty_str(bg.get("motion"), "static")
    out["background"]["atmosphere"] = _nonempty_str(bg.get("atmosphere"), NONE)

    spec = raw.get("spectrum") if isinstance(raw.get("spectrum"), dict) else {}
    out["spectrum"]["shape"] = _nonempty_str(spec.get("shape"), NONE)
    out["spectrum"]["material"] = _nonempty_str(spec.get("material"), NONE)
    out["spectrum"]["animation"] = _nonempty_str(spec.get("animation"), NONE)

    logo = raw.get("logo") if isinstance(raw.get("logo"), dict) else {}
    out["logo"]["enabled"] = bool(logo.get("enabled", True))
    out["logo"]["animation"] = _nonempty_str(logo.get("animation"), NONE)

    text = raw.get("text") if isinstance(raw.get("text"), dict) else {}
    out["text"]["enabled"] = bool(text.get("enabled", False))

    overlay = raw.get("overlay") if isinstance(raw.get("overlay"), dict) else {}
    out["overlay"]["enabled"] = bool(overlay.get("enabled", False))
    out["overlay"]["animation"] = _nonempty_str(overlay.get("animation"), NONE)
    items = overlay.get("items")
    out["overlay"]["items"] = list(items) if isinstance(items, list) else []

    particles = raw.get("particles") if isinstance(raw.get("particles"), dict) else {}
    out["particles"]["type"] = _nonempty_str(particles.get("type"), NONE)
    out["particles"]["behavior"] = _nonempty_str(particles.get("behavior"), NONE)

    lighting = raw.get("lighting") if isinstance(raw.get("lighting"), dict) else {}
    out["lighting"]["effect"] = _nonempty_str(lighting.get("effect"), NONE)
    out["lighting"]["trigger"] = _nonempty_str(lighting.get("trigger"), NONE)

    camera = raw.get("camera") if isinstance(raw.get("camera"), dict) else {}
    out["camera"]["behavior"] = _nonempty_str(camera.get("behavior"), NONE)

    post = raw.get("postProcessing") if isinstance(raw.get("postProcessing"), dict) else {}
    effects = post.get("effects")
    out["postProcessing"]["effects"] = (
        [str(item).strip() for item in effects if str(item).strip()]
        if isinstance(effects, list)
        else []
    )

    audio = raw.get("audio") if isinstance(raw.get("audio"), dict) else {}
    mapping = audio.get("mapping")
    out["audio"]["mapping"] = dict(mapping) if isinstance(mapping, dict) else {}

    return out


def composition_from_legacy_template(template: dict[str, Any] | None) -> dict[str, Any]:
    """Project today’s saved template fields into the composition architecture tree."""
    src = template if isinstance(template, dict) else {}
    out = default_composition_scene()

    bg = src.get("backgroundSettings") if isinstance(src.get("backgroundSettings"), dict) else {}
    motion_legacy = str(bg.get("motionMode") or "none").strip().lower() or "none"
    out["background"]["motion"] = _LEGACY_BG_MOTION_TO_COMPOSITION.get(motion_legacy, motion_legacy)
    out["background"]["image"] = _optional_str(src.get("previewBackground") or bg.get("path"))

    smoke = src.get("effects") if isinstance(src.get("effects"), dict) else {}
    smoke_cfg = smoke.get("smoke") if isinstance(smoke.get("smoke"), dict) else {}
    if bool(smoke_cfg.get("enabled")):
        out["background"]["atmosphere"] = "smoke"

    style = str(src.get("style") or "").strip()
    out["spectrum"]["shape"] = style.lower() if style else NONE

    logo = src.get("logoSettings") if isinstance(src.get("logoSettings"), dict) else {}
    out["logo"]["enabled"] = bool(logo.get("enabled", True))
    if bool(logo.get("spinEnabled")):
        out["logo"]["animation"] = "rotate"

    album = src.get("albumText") if isinstance(src.get("albumText"), dict) else {}
    title = src.get("titleText") if isinstance(src.get("titleText"), dict) else {}
    overlays = src.get("textOverlays") if isinstance(src.get("textOverlays"), list) else []
    text_on = bool(album.get("enabled")) or bool(title.get("enabled")) or any(
        isinstance(item, dict) and bool(item.get("enabled")) for item in overlays
    )
    out["text"]["enabled"] = text_on

    overlay_settings = src.get("overlaySettings") if isinstance(src.get("overlaySettings"), dict) else {}
    overlay_items = overlay_settings.get("items") if isinstance(overlay_settings.get("items"), list) else []
    out["overlay"]["enabled"] = bool(overlay_settings.get("enabled", False)) or bool(overlay_items)
    out["overlay"]["items"] = list(overlay_items)

    particles = src.get("particlesSettings") if isinstance(src.get("particlesSettings"), dict) else {}
    if bool(particles.get("enabled", True)):
        variant = str(particles.get("variant") or particles.get("style") or "").strip()
        out["particles"]["type"] = variant.lower() if variant else NONE
    else:
        out["particles"]["type"] = NONE

    lightning = src.get("lightningLayers") if isinstance(src.get("lightningLayers"), list) else []
    if lightning:
        first = lightning[0] if isinstance(lightning[0], dict) else {}
        effect = str(first.get("style") or "").strip()
        trigger = str(first.get("trigger") or "").strip()
        out["lighting"]["effect"] = effect.lower() if effect else NONE
        out["lighting"]["trigger"] = trigger.lower() if trigger else NONE

    effects = src.get("effects") if isinstance(src.get("effects"), dict) else {}
    shake = effects.get("camera_shake") if isinstance(effects.get("camera_shake"), dict) else {}
    if bool(shake.get("enabled")):
        out["camera"]["behavior"] = "shake"

    post_effects: list[str] = []
    vignette = effects.get("vignette") if isinstance(effects.get("vignette"), dict) else {}
    if bool(vignette.get("enabled")):
        post_effects.append("vignette")
    bloom = effects.get("bloom") if isinstance(effects.get("bloom"), dict) else {}
    if bool(bloom.get("enabled")):
        post_effects.append("bloom")
    rgb = effects.get("rgb_split") if isinstance(effects.get("rgb_split"), dict) else {}
    if bool(rgb.get("enabled")):
        post_effects.append("rgb_split")
    out["postProcessing"]["effects"] = post_effects

    # Audio mapping stays empty in P0 (façade lands in P11); Layer 1 audio object exists.
    out["audio"]["mapping"] = {}

    # P1–P5: preserve orthogonal axes that legacy templates cannot express,
    # and keep composition geometry ids when they are canonical shapes.
    prev = src.get("composition")
    if isinstance(prev, dict) and prev:
        prev_n = normalize_composition_scene(prev)
        out["spectrum"]["material"] = prev_n["spectrum"]["material"]
        out["spectrum"]["animation"] = prev_n["spectrum"]["animation"]
        out["particles"]["behavior"] = prev_n["particles"]["behavior"]
        out["overlay"]["animation"] = prev_n["overlay"]["animation"]
        out["audio"]["mapping"] = deepcopy(prev_n["audio"]["mapping"])
        if prev_n.get("colorPalette"):
            out["colorPalette"] = prev_n.get("colorPalette")
        prev_shape = str(prev_n["spectrum"]["shape"] or "").strip()
        if prev_shape and prev_shape != NONE:
            try:
                from features.video.lib.composition_spectrum_shapes import SPECTRUM_SHAPE_IDS

                # Canonical geometry ids win over legacy style projection.
                # Legacy style ids (orbit-spikes, …) still follow ``style``.
                if prev_shape in SPECTRUM_SHAPE_IDS:
                    out["spectrum"]["shape"] = prev_shape
                elif not style:
                    out["spectrum"]["shape"] = prev_shape
            except Exception:
                if not style:
                    out["spectrum"]["shape"] = prev_shape
        prev_particle_type = str(prev_n["particles"]["type"] or "").strip()
        if prev_particle_type and prev_particle_type != NONE:
            try:
                from features.video.lib.composition_particles import PARTICLE_TYPE_IDS

                # Canonical catalog ids win over bare GPU variant projection.
                if prev_particle_type in PARTICLE_TYPE_IDS:
                    out["particles"]["type"] = prev_particle_type
            except Exception:
                pass
        # Canonical Layer 4 ids win over spinEnabled → rotate projection.
        prev_logo_anim = str(prev_n["logo"]["animation"] or "").strip()
        if prev_logo_anim and prev_logo_anim != NONE:
            try:
                from features.video.lib.composition_animations import ANIMATION_BEHAVIOR_IDS

                if prev_logo_anim in ANIMATION_BEHAVIOR_IDS:
                    out["logo"]["animation"] = prev_logo_anim
            except Exception:
                out["logo"]["animation"] = prev_logo_anim

    return normalize_composition_scene(out)


def ensure_composition_on_template(template: dict[str, Any]) -> dict[str, Any]:
    """Attach normalized ``composition`` without removing legacy GPU fields.

    Always re-projects from legacy aliases (``style``, motionMode, …) while
    preserving orthogonal axes already stored on ``composition`` (P1).
    """
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    template["composition"] = composition_from_legacy_template(template)
    return template


def strip_composition_for_renderer(template: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy without ``composition`` (GPU path ignores authoring tree)."""
    if not isinstance(template, dict):
        return {}
    out = dict(template)
    out.pop("composition", None)
    return out


def legacy_background_motion_mode(composition_motion: str | None) -> str:
    """Map composition.background.motion → backgroundSettings.motionMode."""
    key = str(composition_motion or "static").strip().lower() or "static"
    return _COMPOSITION_BG_MOTION_TO_LEGACY.get(key, key if key in ("none", "zoom", "vibrate") else "none")


def composition_legacy_key_map() -> dict[str, str]:
    """Human/docs map: architecture path → primary legacy template path."""
    return {
        "composition.background.image": "previewBackground / workspace background path / CLI --background",
        "composition.background.motion": "backgroundSettings.motionMode",
        "composition.background.atmosphere": "effects.smoke (+ future atmosphere presets)",
        "composition.spectrum.shape": "style (+ layers[] geometry)",
        "composition.spectrum.material": "(P4) material look packs",
        "composition.spectrum.animation": "(P5) Layer 4 behaviors + audio dial recipes",
        "composition.logo.enabled": "logoSettings.enabled",
        "composition.logo.animation": "(P5) Layer 4 + logoSettings.spinEnabled / motionMode",
        "composition.text.enabled": "albumText / titleText / textOverlays",
        "composition.overlay.enabled": "overlaySettings.enabled (new stub domain)",
        "composition.overlay.animation": "(P5) Layer 4 shared behavior id",
        "composition.overlay.items": "overlaySettings.items (new stub domain)",
        "composition.particles.type": "(P6) catalog id → particlesSettings recipe (variant/style/…)",
        "composition.particles.behavior": "(P5) shared Layer 4 id; independent of type",
        "composition.lighting.effect": "lightningLayers[].style",
        "composition.lighting.trigger": "lightningLayers[].trigger",
        "composition.camera.behavior": "effects.camera_shake (+ future camera library)",
        "composition.postProcessing.effects[]": "effects.vignette / bloom / rgb_split / …",
        "composition.audio.mapping": "(new — P11 Audio Mapping façade)",
        "composition.colorPalette": "(new — P2)",
    }


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _nonempty_str(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default
