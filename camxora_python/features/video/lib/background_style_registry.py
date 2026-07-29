"""Background preset styles — unified dropdown like particles/spectrum."""

from __future__ import annotations

from typing import Any

from features.video.lib.domain_preset_store import (
    clear_domain_preset_override,
    get_domain_preset_override,
    has_domain_preset_override,
    save_domain_preset_override,
)
from features.video.lib.spectrum_style_registry import PACK_PRESET_PREFIX
from features.video.lib.template_draft_domains import pick_background_draft_slice

BACKGROUND_STYLE_PRESETS: tuple[tuple[str, str], ...] = (
    ("cinematic_static", "Cinematic Static"),
    ("bass_pulse_zoom", "Bass Pulse Zoom"),
    ("euphoric_shimmer", "Euphoric Shimmer"),
    ("dark_club", "Dark Club"),
    ("dreamy_drift", "Dreamy Drift"),
)

BACKGROUND_PRESET_FIELD_KEYS: tuple[str, ...] = (
    "backgroundEnabled",
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

_DOMAIN = "background"
_BUILTIN_IDS = frozenset(preset_id for preset_id, _ in BACKGROUND_STYLE_PRESETS)

BACKGROUND_STYLE_PRESET_PATCHES: dict[str, dict[str, Any]] = {
    "cinematic_static": {
        "backgroundEnabled": True,
        "backgroundFitMode": "cover",
        "backgroundUserScale": 1.0,
        "backgroundBrightness": 0.92,
        "backgroundReactivity": 0.0,
        "backgroundSmoothing": 0.85,
        "backgroundMotionMode": "none",
        "backgroundMotionZoomStrength": 1.0,
        "backgroundMotionVibrateStrength": 1.0,
        "backgroundMotionSpeed": 1.0,
        "vignetteEnabled": True,
        "vignetteStrength": 0.42,
        "vignetteFeather": 0.72,
        "vignetteOpacity": 0.55,
        "vignetteColor": "#000000",
        "vignetteReactivity": 1.4,
        "smokeEnabled": False,
        "smokeStrength": 0.35,
        "smokeBlur": 0.55,
        "smokeNoise": 0.55,
        "smokeSpeed": 0.35,
        "smokeOpacity": 0.55,
        "smokeColor": "#000000",
    },
    "bass_pulse_zoom": {
        "backgroundEnabled": True,
        "backgroundFitMode": "cover",
        "backgroundUserScale": 1.05,
        "backgroundBrightness": 1.0,
        "backgroundReactivity": 4.5,
        "backgroundSmoothing": 0.35,
        "backgroundMotionMode": "zoom",
        "backgroundMotionZoomStrength": 6.0,
        "backgroundMotionVibrateStrength": 0.5,
        "backgroundMotionSpeed": 3.2,
        "vignetteEnabled": False,
        "vignetteStrength": 0.35,
        "vignetteFeather": 0.65,
        "vignetteOpacity": 0.65,
        "vignetteColor": "#000000",
        "vignetteReactivity": 0.0,
        "smokeEnabled": False,
        "smokeStrength": 0.35,
        "smokeBlur": 0.55,
        "smokeNoise": 0.55,
        "smokeSpeed": 0.35,
        "smokeOpacity": 0.55,
        "smokeColor": "#000000",
    },
    "euphoric_shimmer": {
        "backgroundEnabled": True,
        "backgroundFitMode": "contain",
        "backgroundUserScale": 1.15,
        "backgroundBrightness": 1.18,
        "backgroundReactivity": 2.0,
        "backgroundSmoothing": 0.55,
        "backgroundMotionMode": "both",
        "backgroundMotionZoomStrength": 2.5,
        "backgroundMotionVibrateStrength": 3.0,
        "backgroundMotionSpeed": 2.0,
        "vignetteEnabled": True,
        "vignetteStrength": 0.25,
        "vignetteFeather": 0.8,
        "vignetteOpacity": 0.35,
        "vignetteColor": "#0a0a1a",
        "vignetteReactivity": 0.8,
        "smokeEnabled": False,
        "smokeStrength": 0.35,
        "smokeBlur": 0.55,
        "smokeNoise": 0.55,
        "smokeSpeed": 0.35,
        "smokeOpacity": 0.55,
        "smokeColor": "#000000",
    },
    "dark_club": {
        "backgroundEnabled": True,
        "backgroundFitMode": "cover",
        "backgroundUserScale": 1.0,
        "backgroundBrightness": 0.72,
        "backgroundReactivity": 1.2,
        "backgroundSmoothing": 0.7,
        "backgroundMotionMode": "vibrate",
        "backgroundMotionZoomStrength": 1.0,
        "backgroundMotionVibrateStrength": 2.8,
        "backgroundMotionSpeed": 1.5,
        "vignetteEnabled": True,
        "vignetteStrength": 0.58,
        "vignetteFeather": 0.55,
        "vignetteOpacity": 0.78,
        "vignetteColor": "#000000",
        "vignetteReactivity": 2.2,
        "smokeEnabled": True,
        "smokeStrength": 0.48,
        "smokeBlur": 0.62,
        "smokeNoise": 0.5,
        "smokeSpeed": 0.28,
        "smokeOpacity": 0.62,
        "smokeColor": "#120818",
    },
    "dreamy_drift": {
        "backgroundEnabled": True,
        "backgroundFitMode": "cover",
        "backgroundUserScale": 1.08,
        "backgroundBrightness": 0.98,
        "backgroundReactivity": 0.6,
        "backgroundSmoothing": 0.88,
        "backgroundMotionMode": "zoom",
        "backgroundMotionZoomStrength": 1.8,
        "backgroundMotionVibrateStrength": 0.2,
        "backgroundMotionSpeed": 0.6,
        "vignetteEnabled": True,
        "vignetteStrength": 0.3,
        "vignetteFeather": 0.85,
        "vignetteOpacity": 0.4,
        "vignetteColor": "#0d1020",
        "vignetteReactivity": 0.6,
        "smokeEnabled": True,
        "smokeStrength": 0.22,
        "smokeBlur": 0.75,
        "smokeNoise": 0.4,
        "smokeSpeed": 0.18,
        "smokeOpacity": 0.35,
        "smokeColor": "#1a1040",
    },
}


def build_background_preset_factory_patch(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    patch = BACKGROUND_STYLE_PRESET_PATCHES.get(key)
    return dict(patch) if patch else None


def is_builtin_background_preset_key(preset_key: str | None) -> bool:
    key = str(preset_key or "").strip()
    return bool(key) and not key.startswith(PACK_PRESET_PREFIX) and key in _BUILTIN_IDS


def resolve_background_preset_patch(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if not is_builtin_background_preset_key(key):
        return None
    stored = get_domain_preset_override(_DOMAIN, key)
    if isinstance(stored, dict):
        return dict(stored)
    return build_background_preset_factory_patch(key)


def capture_background_preset(preset_id: str, draft: dict[str, Any]) -> None:
    key = str(preset_id or "").strip()
    if not is_builtin_background_preset_key(key):
        return
    factory = build_background_preset_factory_patch(key) or {}
    slice_data = pick_background_draft_slice(draft)
    stored = dict(factory)
    for field in BACKGROUND_PRESET_FIELD_KEYS:
        value = slice_data.get(field)
        if value is not None:
            stored[field] = value
    save_domain_preset_override(_DOMAIN, key, stored)


def restore_background_preset_to_factory(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if not is_builtin_background_preset_key(key):
        return None
    clear_domain_preset_override(_DOMAIN, key)
    return build_background_preset_factory_patch(key)


def background_patch_touches_preset_fields(patch: dict[str, Any]) -> bool:
    return any(key in BACKGROUND_PRESET_FIELD_KEYS for key in patch.keys())


def has_background_preset_override(preset_id: str) -> bool:
    key = str(preset_id or "").strip()
    return is_builtin_background_preset_key(key) and has_domain_preset_override(_DOMAIN, key)


def build_unified_background_preset_options(
    catalog_items: list[dict[str, Any]] | None = None,
) -> tuple[tuple[str, str], ...]:
    from features.video.lib.spectrum_style_registry import encode_pack_preset_key

    options: list[tuple[str, str]] = list(BACKGROUND_STYLE_PRESETS)
    for item in catalog_items or []:
        if item.get("domain") != "background":
            continue
        if item.get("status") not in {"ready", "available"}:
            continue
        pack_id = str(item.get("packId") or "").strip()
        version = str(item.get("version") or "").strip()
        name = str(item.get("name") or pack_id).strip()
        if not pack_id or not version:
            continue
        options.append((encode_pack_preset_key(pack_id, version), f"{name} ({version})"))
    return tuple(options)
