"""Logo preset styles — unified dropdown like particles/spectrum."""

from __future__ import annotations

from typing import Any

from features.video.lib.domain_preset_store import (
    clear_domain_preset_override,
    get_domain_preset_override,
    has_domain_preset_override,
    save_domain_preset_override,
)
from features.video.lib.spectrum_style_registry import PACK_PRESET_PREFIX
from features.video.lib.template_draft_domains import pick_logo_draft_slice

LOGO_STYLE_PRESETS: tuple[tuple[str, str], ...] = (
    ("center_hero", "Center Hero"),
    ("vinyl_spin", "Vinyl Spin"),
    ("beat_punch", "Beat Punch"),
    ("watermark_subtle", "Watermark Subtle"),
    ("halo_lock", "Halo Lock"),
)

# Exclude logoPath — file selection is workspace asset, not a style recipe.
LOGO_PRESET_FIELD_KEYS: tuple[str, ...] = (
    "logoEnabled",
    "logoSpinEnabled",
    "logoSpinDirection",
    "logoSpinSpeed",
    "logoShape",
    "logoSizeStep",
    "logoOpacity",
    "logoReactivity",
    "logoSmoothing",
    "logoMotionMode",
    "logoMotionZoomStrength",
    "logoMotionVibrateStrength",
    "logoMotionSpeed",
    "spectrumAttachToLogo",
    "spectrumLogoGap",
)

_DOMAIN = "logo"
_BUILTIN_IDS = frozenset(preset_id for preset_id, _ in LOGO_STYLE_PRESETS)

LOGO_STYLE_PRESET_PATCHES: dict[str, dict[str, Any]] = {
    "center_hero": {
        "logoEnabled": True,
        "logoSpinEnabled": False,
        "logoSpinDirection": "cw",
        "logoSpinSpeed": 0.0,
        "logoShape": "circle",
        "logoSizeStep": 3.5,
        "logoOpacity": 1.0,
        "logoReactivity": 0.4,
        "logoSmoothing": 0.75,
        "logoMotionMode": "none",
        "logoMotionZoomStrength": 1.0,
        "logoMotionVibrateStrength": 1.0,
        "logoMotionSpeed": 1.0,
        "spectrumAttachToLogo": False,
        "spectrumLogoGap": 24.0,
    },
    "vinyl_spin": {
        "logoEnabled": True,
        "logoSpinEnabled": True,
        "logoSpinDirection": "cw",
        "logoSpinSpeed": 360.0,
        "logoShape": "circle",
        "logoSizeStep": 4.0,
        "logoOpacity": 1.0,
        "logoReactivity": 0.2,
        "logoSmoothing": 0.8,
        "logoMotionMode": "none",
        "logoMotionZoomStrength": 1.0,
        "logoMotionVibrateStrength": 1.0,
        "logoMotionSpeed": 1.0,
        "spectrumAttachToLogo": True,
        "spectrumLogoGap": 24.0,
    },
    "beat_punch": {
        "logoEnabled": True,
        "logoSpinEnabled": False,
        "logoSpinDirection": "cw",
        "logoSpinSpeed": 0.0,
        "logoShape": "circle",
        "logoSizeStep": 3.2,
        "logoOpacity": 1.0,
        "logoReactivity": 1.4,
        "logoSmoothing": 0.4,
        "logoMotionMode": "both",
        "logoMotionZoomStrength": 5.5,
        "logoMotionVibrateStrength": 4.0,
        "logoMotionSpeed": 3.5,
        "spectrumAttachToLogo": True,
        "spectrumLogoGap": 20.0,
    },
    "watermark_subtle": {
        "logoEnabled": True,
        "logoSpinEnabled": False,
        "logoSpinDirection": "cw",
        "logoSpinSpeed": 0.0,
        "logoShape": "square",
        "logoSizeStep": 1.4,
        "logoOpacity": 0.55,
        "logoReactivity": 0.15,
        "logoSmoothing": 0.9,
        "logoMotionMode": "none",
        "logoMotionZoomStrength": 1.0,
        "logoMotionVibrateStrength": 1.0,
        "logoMotionSpeed": 1.0,
        "spectrumAttachToLogo": False,
        "spectrumLogoGap": 24.0,
    },
    "halo_lock": {
        "logoEnabled": True,
        "logoSpinEnabled": False,
        "logoSpinDirection": "cw",
        "logoSpinSpeed": 0.0,
        "logoShape": "circle",
        "logoSizeStep": 2.8,
        "logoOpacity": 0.95,
        "logoReactivity": 0.8,
        "logoSmoothing": 0.65,
        "logoMotionMode": "zoom",
        "logoMotionZoomStrength": 2.2,
        "logoMotionVibrateStrength": 0.8,
        "logoMotionSpeed": 1.8,
        "spectrumAttachToLogo": True,
        "spectrumLogoGap": 32.0,
    },
}


def build_logo_preset_factory_patch(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    patch = LOGO_STYLE_PRESET_PATCHES.get(key)
    return dict(patch) if patch else None


def is_builtin_logo_preset_key(preset_key: str | None) -> bool:
    key = str(preset_key or "").strip()
    return bool(key) and not key.startswith(PACK_PRESET_PREFIX) and key in _BUILTIN_IDS


def resolve_logo_preset_patch(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if not is_builtin_logo_preset_key(key):
        return None
    stored = get_domain_preset_override(_DOMAIN, key)
    if isinstance(stored, dict):
        return dict(stored)
    return build_logo_preset_factory_patch(key)


def capture_logo_preset(preset_id: str, draft: dict[str, Any]) -> None:
    key = str(preset_id or "").strip()
    if not is_builtin_logo_preset_key(key):
        return
    factory = build_logo_preset_factory_patch(key) or {}
    slice_data = pick_logo_draft_slice(draft)
    stored = dict(factory)
    for field in LOGO_PRESET_FIELD_KEYS:
        value = slice_data.get(field)
        if value is not None:
            stored[field] = value
    save_domain_preset_override(_DOMAIN, key, stored)


def restore_logo_preset_to_factory(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if not is_builtin_logo_preset_key(key):
        return None
    clear_domain_preset_override(_DOMAIN, key)
    return build_logo_preset_factory_patch(key)


def logo_patch_touches_preset_fields(patch: dict[str, Any]) -> bool:
    return any(key in LOGO_PRESET_FIELD_KEYS for key in patch.keys())


def has_logo_preset_override(preset_id: str) -> bool:
    key = str(preset_id or "").strip()
    return is_builtin_logo_preset_key(key) and has_domain_preset_override(_DOMAIN, key)


def build_unified_logo_preset_options(
    catalog_items: list[dict[str, Any]] | None = None,
) -> tuple[tuple[str, str], ...]:
    from features.video.lib.spectrum_style_registry import encode_pack_preset_key

    options: list[tuple[str, str]] = list(LOGO_STYLE_PRESETS)
    for item in catalog_items or []:
        if item.get("domain") != "logo":
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
