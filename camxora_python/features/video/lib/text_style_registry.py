"""Text style presets — unified architecture with local JSON overrides."""

from __future__ import annotations

from typing import Any

from features.video.lib.domain_preset_store import (
    clear_domain_preset_override,
    get_domain_preset_override,
    has_domain_preset_override,
    save_domain_preset_override,
)
from features.video.lib.text_overlay_presets import (
    build_neon_brush_stack_overlays,
    build_text_preset_style,
    clone_text_overlays,
)
from features.video.lib.video_template_draft import build_default_text_overlay_draft

TEXT_STYLE_PRESETS: tuple[tuple[str, str], ...] = (
    ("neon_outline", "Neon Outline"),
    ("soft_glow", "Soft Glow"),
    ("dark_stroke", "Dark Stroke"),
    ("lower_third_title", "Lower Third Title"),
    ("kinetic_shout", "Kinetic Shout"),
    ("neon_brush_stack", "Neon Brush Stack"),
)

# Style fields remembered for single-layer presets (text content preserved on apply).
TEXT_STYLE_FIELD_KEYS: tuple[str, ...] = (
    "fontSize",
    "color",
    "strokeColor",
    "strokeWidth",
    "shadow",
    "animation",
    "anchor",
    "x",
    "y",
)

_DOMAIN = "text"
_BUILTIN_IDS = frozenset(preset_id for preset_id, _ in TEXT_STYLE_PRESETS)
_STACK_PRESET = "neon_brush_stack"

TEXT_STYLE_PRESET_PATCHES: dict[str, dict[str, Any]] = {
    "neon_outline": {
        "fontSize": 72,
        "color": "#ffffff",
        "strokeColor": "#ff4fd8",
        "strokeWidth": 3,
        "shadow": 0.45,
        "animation": "pop",
        "anchor": "center",
        "x": 0,
        "y": 0,
    },
    "soft_glow": {
        "fontSize": 58,
        "color": "#dff6ff",
        "strokeColor": "#051229",
        "strokeWidth": 1.5,
        "shadow": 0.6,
        "animation": "fade",
        "anchor": "center",
        "x": 0,
        "y": 0,
    },
    "dark_stroke": {
        "fontSize": 62,
        "color": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 4,
        "shadow": 0.35,
        "animation": "fade",
        "anchor": "center",
        "x": 0,
        "y": 0,
    },
    "lower_third_title": {
        "fontSize": 54,
        "color": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 2.5,
        "shadow": 0.5,
        "animation": "slide_up",
        "anchor": "bottom-left",
        "x": 48,
        "y": 120,
    },
    "kinetic_shout": {
        "fontSize": 96,
        "color": "#fff200",
        "strokeColor": "#1a0a00",
        "strokeWidth": 3.5,
        "shadow": 0.55,
        "animation": "shake",
        "anchor": "center",
        "x": 0,
        "y": 0,
    },
}


def is_builtin_text_preset_key(preset_key: str | None) -> bool:
    return str(preset_key or "").strip() in _BUILTIN_IDS


def is_text_stack_preset(preset_key: str | None) -> bool:
    return str(preset_key or "").strip() == _STACK_PRESET


def build_text_preset_factory_style(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if key == _STACK_PRESET:
        return None
    if key in TEXT_STYLE_PRESET_PATCHES:
        return dict(TEXT_STYLE_PRESET_PATCHES[key])
    legacy = build_text_preset_style(key)
    return dict(legacy) if legacy else None


def resolve_text_preset_style(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if not is_builtin_text_preset_key(key) or key == _STACK_PRESET:
        return None
    stored = get_domain_preset_override(_DOMAIN, key)
    if isinstance(stored, dict) and "style" in stored and isinstance(stored["style"], dict):
        return dict(stored["style"])
    if isinstance(stored, dict) and any(k in stored for k in TEXT_STYLE_FIELD_KEYS):
        return {k: stored[k] for k in TEXT_STYLE_FIELD_KEYS if k in stored}
    return build_text_preset_factory_style(key)


def resolve_text_stack_overlays(preset_id: str) -> list[dict[str, Any]] | None:
    key = str(preset_id or "").strip()
    if key != _STACK_PRESET:
        return None
    stored = get_domain_preset_override(_DOMAIN, key)
    if isinstance(stored, dict) and isinstance(stored.get("overlays"), list):
        return clone_text_overlays(stored["overlays"])
    return build_neon_brush_stack_overlays()


def capture_text_preset(
    preset_id: str,
    *,
    overlays: list[dict[str, Any]],
    selected_index: int,
) -> None:
    key = str(preset_id or "").strip()
    if not is_builtin_text_preset_key(key):
        return
    if key == _STACK_PRESET:
        save_domain_preset_override(_DOMAIN, key, {"overlays": clone_text_overlays(overlays)})
        return
    if not overlays or not (0 <= selected_index < len(overlays)):
        return
    selected = overlays[selected_index]
    if not isinstance(selected, dict):
        return
    factory = build_text_preset_factory_style(key) or {}
    style = dict(factory)
    for field in TEXT_STYLE_FIELD_KEYS:
        if field in selected and selected.get(field) is not None:
            style[field] = selected[field]
    save_domain_preset_override(_DOMAIN, key, {"style": style})


def restore_text_preset_to_factory(preset_id: str) -> bool:
    key = str(preset_id or "").strip()
    if not is_builtin_text_preset_key(key):
        return False
    return clear_domain_preset_override(_DOMAIN, key)


def has_text_preset_override(preset_id: str) -> bool:
    key = str(preset_id or "").strip()
    return is_builtin_text_preset_key(key) and has_domain_preset_override(_DOMAIN, key)


def apply_resolved_text_preset(
    overlays: list[dict[str, Any]],
    preset: str,
    *,
    selected_index: int,
) -> tuple[list[dict[str, Any]], int]:
    """Apply factory or local override text preset to overlays."""
    key = str(preset or "").strip()
    if key == _STACK_PRESET:
        stack = resolve_text_stack_overlays(key) or []
        next_overlays = [*overlays, *stack]
        return next_overlays, len(next_overlays) - 1

    style = resolve_text_preset_style(key)
    if not style:
        return overlays, selected_index

    if overlays and 0 <= selected_index < len(overlays):
        selected = dict(overlays[selected_index])
        selected.update(style)
        next_overlays = list(overlays)
        next_overlays[selected_index] = selected
        return next_overlays, selected_index

    next_overlay = {**build_default_text_overlay_draft(), "enabled": True, **style}
    next_overlays = [*overlays, next_overlay]
    return next_overlays, len(next_overlays) - 1
