"""Text fill color engine — solid / gradient / neon (Album + Title)."""

from __future__ import annotations

from typing import Any

from features.video.lib.spectrum_color_engine import (
    MAX_GRADIENT_COLOR_STOPS,
    normalize_spectrum_gradient_colors,
)
from features.video.lib.template_value_utils import normalize_color, to_record, to_string_value

TEXT_FILL_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("solid", "Solid"),
    ("gradient", "Gradient"),
    ("neon", "Neon"),
)

TEXT_GLOW_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("solid", "Solid"),
    ("gradient", "Gradient"),
)

TEXT_GRADIENT_DIRECTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("vertical", "Vertical"),
    ("horizontal", "Horizontal"),
    ("diagonal", "Diagonal"),
)

VALID_TEXT_FILL_MODES = frozenset(key for key, _ in TEXT_FILL_MODE_OPTIONS)
VALID_TEXT_GLOW_MODES = frozenset(key for key, _ in TEXT_GLOW_MODE_OPTIONS)
VALID_TEXT_GRADIENT_DIRECTIONS = frozenset(key for key, _ in TEXT_GRADIENT_DIRECTION_OPTIONS)

DEFAULT_GLOW_COLOR = "#ff4fd8"
DEFAULT_GRADIENT_COLORS = ("#ffffff", "#22d3ee")
DEFAULT_GLOW_GRADIENT_COLORS = ("#ff1a3c", "#ff6a00")


def normalize_text_fill_mode(raw: Any, fallback: str = "solid") -> str:
    mode = to_string_value(raw, fallback).lower().strip()
    if mode not in VALID_TEXT_FILL_MODES:
        return fallback if fallback in VALID_TEXT_FILL_MODES else "solid"
    return mode


def normalize_text_gradient_direction(raw: Any, fallback: str = "vertical") -> str:
    direction = to_string_value(raw, fallback).lower().strip()
    # Accept spectrum-style aliases used elsewhere in the app.
    aliases = {
        "top-to-bottom": "vertical",
        "left-to-right": "horizontal",
        "bottom-to-top": "vertical",
        "right-to-left": "horizontal",
    }
    direction = aliases.get(direction, direction)
    if direction not in VALID_TEXT_GRADIENT_DIRECTIONS:
        return fallback if fallback in VALID_TEXT_GRADIENT_DIRECTIONS else "vertical"
    return direction


def normalize_text_gradient_colors(
    raw_colors: list[Any] | None,
    fallback: str,
    *,
    require_stops: bool = False,
) -> list[str]:
    """Normalize gradient stops for text fill.

    When ``require_stops`` is False and the list is empty, keep it empty so
    solid/neon presets do not invent fake stops on round-trip.
    """
    colors = list(raw_colors or []) if isinstance(raw_colors, list) else []
    if not require_stops and len(colors) == 0:
        return []
    return normalize_spectrum_gradient_colors(colors, fallback)[:MAX_GRADIENT_COLOR_STOPS]


def normalize_text_glow_color(raw: Any, fallback: str = DEFAULT_GLOW_COLOR) -> str:
    return normalize_color(raw, fallback)


def normalize_text_glow_mode(raw: Any, fallback: str = "solid") -> str:
    mode = to_string_value(raw, fallback).lower().strip()
    if mode not in VALID_TEXT_GLOW_MODES:
        return fallback if fallback in VALID_TEXT_GLOW_MODES else "solid"
    return mode


def extract_text_color_model(style: dict[str, Any] | None) -> dict[str, Any]:
    """Extract fill-mode color fields from an album/title style dict."""
    record = to_record(style)
    nested = to_record(record.get("colorMeta"))
    solid = normalize_color(
        record.get("color") if not isinstance(record.get("color"), dict) else nested.get("solidColor"),
        "#ffffff",
    )
    fill_mode = normalize_text_fill_mode(
        record.get("fillMode") or nested.get("fillMode") or nested.get("mode"),
        "solid",
    )
    gradient_raw = record.get("gradientColors")
    if gradient_raw is None:
        gradient_raw = nested.get("gradientColors")
    gradient_colors = normalize_text_gradient_colors(
        list(gradient_raw or []) if isinstance(gradient_raw, list) else [],
        solid,
        require_stops=(fill_mode == "gradient"),
    )
    if fill_mode == "gradient" and len(gradient_colors) < 2:
        gradient_colors = normalize_text_gradient_colors(
            list(DEFAULT_GRADIENT_COLORS),
            solid,
            require_stops=True,
        )
    direction = normalize_text_gradient_direction(
        record.get("gradientDirection") or nested.get("gradientDirection"),
        "vertical",
    )
    glow_color = normalize_text_glow_color(
        record.get("glowColor") or nested.get("glowColor"),
        DEFAULT_GLOW_COLOR if fill_mode == "neon" else solid,
    )
    glow_mode = normalize_text_glow_mode(
        record.get("glowMode") or nested.get("glowMode"),
        "solid",
    )
    glow_grad_raw = record.get("glowGradientColors")
    if glow_grad_raw is None:
        glow_grad_raw = nested.get("glowGradientColors")
    glow_gradient_colors = normalize_text_gradient_colors(
        list(glow_grad_raw or []) if isinstance(glow_grad_raw, list) else [],
        glow_color,
        require_stops=(glow_mode == "gradient"),
    )
    if glow_mode == "gradient" and len(glow_gradient_colors) < 2:
        glow_gradient_colors = normalize_text_gradient_colors(
            list(DEFAULT_GLOW_GRADIENT_COLORS),
            glow_color,
            require_stops=True,
        )
    glow_direction = normalize_text_gradient_direction(
        record.get("glowGradientDirection") or nested.get("glowGradientDirection"),
        "horizontal",
    )
    return {
        "fillMode": fill_mode,
        "solidColor": solid,
        "gradientColors": gradient_colors,
        "gradientDirection": direction,
        "glowColor": glow_color,
        "glowMode": glow_mode,
        "glowGradientColors": glow_gradient_colors,
        "glowGradientDirection": glow_direction,
    }


def apply_text_color_style_patch(
    style: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    current = extract_text_color_model(style)
    next_mode = (
        current["fillMode"]
        if patch.get("fillMode") is None and patch.get("mode") is None
        else normalize_text_fill_mode(
            patch.get("fillMode") if patch.get("fillMode") is not None else patch.get("mode"),
            current["fillMode"],
        )
    )
    if patch.get("fillMode") is None and patch.get("mode") is None and patch.get("gradientColors") is not None:
        colors = [c for c in list(patch.get("gradientColors") or []) if c]
        if len(colors) >= 2:
            next_mode = "gradient"
    next_solid = (
        current["solidColor"]
        if patch.get("solidColor") is None and patch.get("color") is None
        else normalize_color(
            patch.get("solidColor") if patch.get("solidColor") is not None else patch.get("color"),
            current["solidColor"],
        )
    )
    next_gradient = (
        current["gradientColors"]
        if patch.get("gradientColors") is None
        else normalize_text_gradient_colors(
            list(patch.get("gradientColors") or []),
            next_solid,
            require_stops=(next_mode == "gradient"),
        )
    )
    next_direction = (
        current["gradientDirection"]
        if patch.get("gradientDirection") is None
        else normalize_text_gradient_direction(patch.get("gradientDirection"), current["gradientDirection"])
    )
    next_glow = (
        current["glowColor"]
        if patch.get("glowColor") is None
        else normalize_text_glow_color(patch.get("glowColor"), current["glowColor"])
    )
    next_glow_mode = (
        current["glowMode"]
        if patch.get("glowMode") is None
        else normalize_text_glow_mode(patch.get("glowMode"), current["glowMode"])
    )
    if patch.get("glowMode") is None and patch.get("glowGradientColors") is not None:
        glow_stops = [c for c in list(patch.get("glowGradientColors") or []) if c]
        if len(glow_stops) >= 2:
            next_glow_mode = "gradient"
    next_glow_gradient = (
        current["glowGradientColors"]
        if patch.get("glowGradientColors") is None
        else normalize_text_gradient_colors(
            list(patch.get("glowGradientColors") or []),
            next_glow,
            require_stops=(next_glow_mode == "gradient"),
        )
    )
    next_glow_direction = (
        current["glowGradientDirection"]
        if patch.get("glowGradientDirection") is None
        else normalize_text_gradient_direction(
            patch.get("glowGradientDirection"),
            current["glowGradientDirection"],
        )
    )
    nested = to_record(style.get("colorMeta"))
    return {
        **style,
        "color": next_solid,
        "fillMode": next_mode,
        "gradientColors": next_gradient,
        "gradientDirection": next_direction,
        "glowColor": next_glow,
        "glowMode": next_glow_mode,
        "glowGradientColors": next_glow_gradient,
        "glowGradientDirection": next_glow_direction,
        "colorMeta": {
            **nested,
            "fillMode": next_mode,
            "mode": next_mode,
            "solidColor": next_solid,
            "gradientColors": next_gradient,
            "gradientDirection": next_direction,
            "glowColor": next_glow,
            "glowMode": next_glow_mode,
            "glowGradientColors": next_glow_gradient,
            "glowGradientDirection": next_glow_direction,
        },
    }


def text_color_fields_from_model(model: dict[str, Any]) -> dict[str, Any]:
    """Flat style keys for draft/save from an extracted color model."""
    return {
        "fillMode": model["fillMode"],
        "color": model["solidColor"],
        "gradientColors": list(model["gradientColors"]),
        "gradientDirection": model["gradientDirection"],
        "glowColor": model["glowColor"],
        "glowMode": model["glowMode"],
        "glowGradientColors": list(model["glowGradientColors"]),
        "glowGradientDirection": model["glowGradientDirection"],
    }


def default_text_color_fields() -> dict[str, Any]:
    return {
        "fillMode": "solid",
        "gradientColors": [],
        "gradientDirection": "vertical",
        "glowColor": DEFAULT_GLOW_COLOR,
        "glowMode": "solid",
        "glowGradientColors": [],
        "glowGradientDirection": "horizontal",
    }
