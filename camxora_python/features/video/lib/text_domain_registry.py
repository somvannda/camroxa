"""Album + Title text domains — Spectrum-parity presets and marketplace contract.

Template keys:
- albumText { enabled, contentMode, manualText, style, ... }
- titleText { enabled, contentMode, listStyle, layout, manualTitles, style,
              listColor, listActiveColor, listActiveIndex, ... }
- effectPacks.album / effectPacks.title
"""

from __future__ import annotations

from typing import Any

from features.video.lib.domain_preset_store import (
    clear_domain_preset_override,
    get_domain_preset_override,
    has_domain_preset_override,
    save_domain_preset_override,
)
from features.video.lib.system_fonts import BUILTIN_FONT_OPTIONS, list_font_options
from features.video.lib.template_value_utils import (
    normalize_color,
    to_boolean,
    to_number,
    to_record,
    to_string_value,
)
from features.video.lib.text_color_engine import (
    DEFAULT_GLOW_COLOR,
    extract_text_color_model,
    text_color_fields_from_model,
)

# Kept for older templates; UI now uses TEXT_ALIGN_OPTIONS (position is drag/x/y).
ANCHOR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("top-left", "Top Left"),
    ("top", "Top"),
    ("top-right", "Top Right"),
    ("left", "Left"),
    ("center", "Center"),
    ("right", "Right"),
    ("bottom-left", "Bottom Left"),
    ("bottom", "Bottom"),
    ("bottom-right", "Bottom Right"),
)

TEXT_ALIGN_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left", "Left"),
    ("center", "Center"),
    ("right", "Right"),
    ("justify", "Justify"),
)

CONTENT_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("pipeline", "From pipeline / tracks"),
    ("manual", "Manual"),
)

TITLE_LIST_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("number", "1. 2. 3."),
    ("number_pad", "01. 02. 03."),
    ("bullet", "Bullet"),
    ("dash", "Dash"),
    ("plain", "Plain"),
)

TITLE_NUMBER_INDENT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("aligned", "Aligned (01. 02. 10.)"),
    ("flush", "Flush (1. 2. 10.)"),
)

TITLE_LAYOUT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("column", "List"),
    ("grid2_td", "2 columns"),
    ("grid2_lr", "2 columns · rows"),
    ("grid3_td", "3 columns"),
    ("grid3_lr", "3 columns · rows"),
)

# Builtin shortlist; inspectors use list_font_options() for the full PC font list.
FONT_OPTIONS: tuple[tuple[str, str], ...] = BUILTIN_FONT_OPTIONS


def get_font_options() -> tuple[tuple[str, str], ...]:
    """Builtin fonts + every installed system family."""
    return list_font_options()

TEXT_DOMAIN_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("neon_glow", "Neon Glow"),
    ("bubble_3d", "Bubble 3D"),
    ("chrome_caption", "Chrome Caption"),
    ("soft_glow", "Soft Glow"),
    ("hard_border", "Hard Border"),
    ("lower_third", "Lower Third Plate"),
    ("kinetic_shout", "Kinetic Shout"),
    ("midnight_stack", "Midnight Stack"),
    ("orange_fire_3d", "Orange Fire 3D"),
    ("glass_outline", "Glass Outline"),
)

# Old preset ids → closest new builtin (resolve/capture still work for saved drafts).
_TEXT_DOMAIN_PRESET_ALIASES: dict[str, str] = {
    "neon_outline": "neon_glow",
    "dark_stroke": "hard_border",
    "clean_serif": "chrome_caption",
}

_STYLE_KEYS: tuple[str, ...] = (
    "fontFamily",
    "fontSize",
    "bold",
    "italic",
    "color",
    "fillMode",
    "gradientColors",
    "gradientDirection",
    "glowColor",
    "glowMode",
    "glowGradientColors",
    "glowGradientDirection",
    "strokeColor",
    "strokeWidth",
    "shadow",
    "shadowBlur",
    "glow",
    "glowBlur",
    "extrudeDepth",
    "extrudeColor",
    "letterSpacing",
    "lineSpacing",
    "boxWidth",
    "align",
    "anchor",
    "x",
    "y",
    "opacity",
)

_DEFAULT_STYLE: dict[str, Any] = {
    "fontFamily": "arial",
    "fontSize": 10,
    "bold": False,
    "italic": False,
    "color": "#ffffff",
    "fillMode": "solid",
    "gradientColors": [],
    "gradientDirection": "vertical",
    "glowColor": DEFAULT_GLOW_COLOR,
    "glowMode": "solid",
    "glowGradientColors": [],
    "glowGradientDirection": "horizontal",
    "strokeColor": "#000000",
    "strokeWidth": 0.0,
    "shadow": 0.0,
    "shadowBlur": 0.0,
    "glow": 0.0,
    "glowBlur": 8.0,
    "extrudeDepth": 0.0,
    "extrudeColor": "#1a1a1a",
    "letterSpacing": 0.0,
    "lineSpacing": 1.2,
    "boxWidth": 0.0,
    "align": "left",
    "anchor": "top-left",
    "x": 0,
    "y": 48,
    "opacity": 1.0,
}

TEXT_DOMAIN_PRESET_PATCHES: dict[str, dict[str, Any]] = {
    "neon_glow": {
        "fontFamily": "segoeuib",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#ffffff",
        "fillMode": "neon",
        "gradientColors": [],
        "gradientDirection": "vertical",
        "glowColor": "#ff1a3c",
        "glowMode": "gradient",
        "glowGradientColors": ["#ff1a3c", "#ff6a00"],
        "glowGradientDirection": "horizontal",
        "strokeColor": "#1a0520",
        "strokeWidth": 0.0,
        "shadow": 0.0,
        "shadowBlur": 0.0,
        "glow": 0.85,
        "glowBlur": 14.0,
        "extrudeDepth": 0.0,
        "extrudeColor": "#1a0520",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 56,
        "opacity": 1.0,
    },
    "bubble_3d": {
        "fontFamily": "arialbd",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#ffffff",
        "fillMode": "solid",
        "gradientColors": [],
        "gradientDirection": "vertical",
        "glowColor": "#ffffff",
        "strokeColor": "#0d1b2a",
        "strokeWidth": 1.0,
        "shadow": 0.55,
        "shadowBlur": 6.0,
        "glow": 0.15,
        "glowBlur": 6.0,
        "extrudeDepth": 2.0,
        "extrudeColor": "#3d5a80",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 48,
        "opacity": 1.0,
    },
    "chrome_caption": {
        "fontFamily": "segoeuib",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#e8f4ff",
        "fillMode": "gradient",
        "gradientColors": ["#f8fbff", "#9eb6d4", "#cfd9e6"],
        "gradientDirection": "vertical",
        "glowColor": "#a8c4e8",
        "strokeColor": "#0a1a2e",
        "strokeWidth": 1.0,
        "shadow": 0.45,
        "shadowBlur": 3.0,
        "glow": 0.2,
        "glowBlur": 6.0,
        "extrudeDepth": 0.0,
        "extrudeColor": "#0a1a2e",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 40,
        "opacity": 1.0,
    },
    "soft_glow": {
        "fontFamily": "segoeui",
        "fontSize": 10,
        "bold": False,
        "italic": False,
        "color": "#dff6ff",
        "fillMode": "neon",
        "gradientColors": [],
        "gradientDirection": "vertical",
        "glowColor": "#7dd3fc",
        "strokeColor": "#051229",
        "strokeWidth": 1.0,
        "shadow": 0.25,
        "shadowBlur": 4.0,
        "glow": 0.45,
        "glowBlur": 8.0,
        "extrudeDepth": 0.0,
        "extrudeColor": "#051229",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 48,
        "opacity": 1.0,
    },
    "hard_border": {
        "fontFamily": "arialbd",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#ffffff",
        "fillMode": "solid",
        "gradientColors": [],
        "gradientDirection": "vertical",
        "glowColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 1.5,
        "shadow": 0.2,
        "shadowBlur": 0.0,
        "glow": 0.0,
        "glowBlur": 4.0,
        "extrudeDepth": 0.0,
        "extrudeColor": "#000000",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 48,
        "opacity": 1.0,
    },
    "lower_third": {
        "fontFamily": "segoeuib",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#ffffff",
        "fillMode": "solid",
        "gradientColors": [],
        "gradientDirection": "horizontal",
        "glowColor": "#ffffff",
        "strokeColor": "#000000",
        "strokeWidth": 1.0,
        "shadow": 0.55,
        "shadowBlur": 4.0,
        "glow": 0.1,
        "glowBlur": 6.0,
        "extrudeDepth": 1.0,
        "extrudeColor": "#111111",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 48,
        "y": 96,
        "opacity": 1.0,
    },
    "kinetic_shout": {
        "fontFamily": "impact",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#fff200",
        "fillMode": "solid",
        "gradientColors": [],
        "gradientDirection": "vertical",
        "glowColor": "#ff8800",
        "strokeColor": "#1a0a00",
        "strokeWidth": 1.5,
        "shadow": 0.5,
        "shadowBlur": 2.0,
        "glow": 0.35,
        "glowBlur": 8.0,
        "extrudeDepth": 1.0,
        "extrudeColor": "#5c2200",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 0,
        "opacity": 1.0,
    },
    "midnight_stack": {
        "fontFamily": "arialbd",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#b8c7ff",
        "fillMode": "solid",
        "gradientColors": [],
        "gradientDirection": "vertical",
        "glowColor": "#7c8cff",
        "strokeColor": "#050814",
        "strokeWidth": 1.0,
        "shadow": 0.45,
        "shadowBlur": 3.0,
        "glow": 0.25,
        "glowBlur": 8.0,
        "extrudeDepth": 0.0,
        "extrudeColor": "#050814",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 64,
        "y": 0,
        "opacity": 1.0,
    },
    "orange_fire_3d": {
        "fontFamily": "segoeuib",
        "fontSize": 10,
        "bold": True,
        "italic": False,
        "color": "#ffb347",
        "fillMode": "gradient",
        "gradientColors": ["#fff7ae", "#ff8c00", "#ff4500"],
        "gradientDirection": "vertical",
        "glowColor": "#ff6a00",
        "strokeColor": "#2a0a00",
        "strokeWidth": 1.0,
        "shadow": 0.5,
        "shadowBlur": 4.0,
        "glow": 0.35,
        "glowBlur": 6.0,
        "extrudeDepth": 2.0,
        "extrudeColor": "#8b2500",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 52,
        "opacity": 1.0,
    },
    "glass_outline": {
        "fontFamily": "segoeui",
        "fontSize": 10,
        "bold": False,
        "italic": False,
        "color": "#f0f7ff",
        "fillMode": "neon",
        "gradientColors": [],
        "gradientDirection": "horizontal",
        "glowColor": "#a5f3fc",
        "strokeColor": "#e0f2fe",
        "strokeWidth": 1.0,
        "shadow": 0.4,
        "shadowBlur": 5.0,
        "glow": 0.55,
        "glowBlur": 5.0,
        "extrudeDepth": 0.0,
        "extrudeColor": "#0c4a6e",
        "letterSpacing": 0.0,
        "lineSpacing": 1.2,
        "boxWidth": 0.0,
        "align": "left",
        "anchor": "top-left",
        "x": 0,
        "y": 48,
        "opacity": 0.95,
    },
}

_BUILTIN_IDS = frozenset(preset_id for preset_id, _ in TEXT_DOMAIN_PRESET_OPTIONS)


def _canonical_preset_id(preset_id: str | None) -> str:
    key = str(preset_id or "").strip()
    return _TEXT_DOMAIN_PRESET_ALIASES.get(key, key)


def default_text_style() -> dict[str, Any]:
    return dict(_DEFAULT_STYLE)


def normalize_text_style(raw: Any) -> dict[str, Any]:
    src = to_record(raw)
    base = default_text_style()
    font = to_string_value(src.get("fontFamily"), base["fontFamily"])
    # Accept any installed family; only fall back when empty.
    if not font.strip():
        font = base["fontFamily"]
    raw_align = src.get("align")
    has_explicit_align = raw_align is not None and str(raw_align).strip() != ""
    align = to_string_value(raw_align, base.get("align", "left")).lower() if has_explicit_align else ""
    if align not in {key for key, _ in TEXT_ALIGN_OPTIONS}:
        # Migrate old screen-anchor values into horizontal text alignment.
        legacy = to_string_value(src.get("anchor"), "").lower()
        if "right" in legacy:
            align = "right"
        elif legacy in {"center", "top", "bottom"} or legacy.endswith("center"):
            align = "center"
        else:
            align = "left"
    # Position is drag/x/y — keep a stable top-left pin for the GPU quad.
    # Alignment only affects glyph layout inside the text box.
    anchor = "top-left"
    color_model = extract_text_color_model({**base, **src})
    color_fields = text_color_fields_from_model(color_model)
    return {
        "fontFamily": font,
        "fontSize": float(max(5.0, min(200.0, to_number(src.get("fontSize"), base["fontSize"])))),
        "bold": to_boolean(src.get("bold"), base["bold"]),
        "italic": to_boolean(src.get("italic"), base["italic"]),
        "color": color_fields["color"],
        "fillMode": color_fields["fillMode"],
        "gradientColors": color_fields["gradientColors"],
        "gradientDirection": color_fields["gradientDirection"],
        "glowColor": color_fields["glowColor"],
        "glowMode": color_fields["glowMode"],
        "glowGradientColors": color_fields["glowGradientColors"],
        "glowGradientDirection": color_fields["glowGradientDirection"],
        "strokeColor": normalize_color(src.get("strokeColor"), base["strokeColor"]),
        "strokeWidth": float(max(0.0, min(12.0, to_number(src.get("strokeWidth"), base["strokeWidth"])))),
        "shadow": float(max(0.0, min(1.0, to_number(src.get("shadow"), base["shadow"])))),
        "shadowBlur": float(max(0.0, min(40.0, to_number(src.get("shadowBlur"), base["shadowBlur"])))),
        "glow": float(max(0.0, min(1.0, to_number(src.get("glow"), base["glow"])))),
        "glowBlur": float(max(0.0, min(48.0, to_number(src.get("glowBlur"), base["glowBlur"])))),
        "extrudeDepth": float(max(0.0, min(24.0, to_number(src.get("extrudeDepth"), base["extrudeDepth"])))),
        "extrudeColor": normalize_color(src.get("extrudeColor"), base["extrudeColor"]),
        "letterSpacing": float(max(-20.0, min(40.0, to_number(src.get("letterSpacing"), base["letterSpacing"])))),
        "lineSpacing": float(max(0.8, min(2.5, to_number(src.get("lineSpacing"), base["lineSpacing"])))),
        "boxWidth": float(max(0.0, min(2000.0, to_number(src.get("boxWidth"), base.get("boxWidth", 0.0))))),
        "align": align,
        "anchor": anchor,
        "x": float(to_number(src.get("x"), base["x"])),
        "y": float(to_number(src.get("y"), base["y"])),
        "opacity": float(max(0.0, min(1.0, to_number(src.get("opacity"), base["opacity"])))),
    }


def default_album_text_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "contentMode": "pipeline",
        "manualText": "",
        "stylePreset": "neon_glow",
        "style": default_text_style(),
    }


def default_title_text_settings() -> dict[str, Any]:
    style = default_text_style()
    style.update({"fontSize": 10.0, "align": "left", "anchor": "top-left", "x": 64, "y": 0, "lineSpacing": 1.2})
    return {
        "enabled": False,
        "contentMode": "pipeline",
        "listStyle": "number",
        "numberIndent": "aligned",
        "layout": "column",
        "manualTitles": [],
        "listColor": "#c4b5fd",
        "listActiveColor": "#fde047",
        "listActiveIndex": 0,
        "stylePreset": "midnight_stack",
        "style": style,
    }


def _normalize_preset_key(raw: Any, fallback: str) -> str:
    preset = _canonical_preset_id(to_string_value(raw, fallback))
    if preset not in _BUILTIN_IDS:
        return fallback
    return preset


def normalize_album_text_settings(raw: Any) -> dict[str, Any]:
    src = to_record(raw)
    base = default_album_text_settings()
    mode = to_string_value(src.get("contentMode"), base["contentMode"]).lower()
    if mode not in {"pipeline", "manual"}:
        mode = "pipeline"
    return {
        "enabled": to_boolean(src.get("enabled"), base["enabled"]),
        "contentMode": mode,
        "manualText": to_string_value(src.get("manualText"), base["manualText"]),
        "stylePreset": _normalize_preset_key(src.get("stylePreset"), base["stylePreset"]),
        "style": normalize_text_style(src.get("style") or base["style"]),
    }


def normalize_title_text_settings(raw: Any) -> dict[str, Any]:
    src = to_record(raw)
    base = default_title_text_settings()
    mode = to_string_value(src.get("contentMode"), base["contentMode"]).lower()
    if mode not in {"pipeline", "manual"}:
        mode = "pipeline"
    list_style = to_string_value(src.get("listStyle"), base["listStyle"]).lower()
    if list_style not in {key for key, _ in TITLE_LIST_STYLE_OPTIONS}:
        list_style = "number"
    number_indent = to_string_value(src.get("numberIndent"), base["numberIndent"]).lower()
    if number_indent not in {key for key, _ in TITLE_NUMBER_INDENT_OPTIONS}:
        number_indent = "aligned"
    layout = to_string_value(src.get("layout"), base["layout"]).lower()
    if layout not in {key for key, _ in TITLE_LAYOUT_OPTIONS}:
        layout = "column"
    manual = src.get("manualTitles")
    titles: list[str] = []
    if isinstance(manual, list):
        titles = [str(item).strip() for item in manual if str(item).strip()]
    elif isinstance(manual, str) and manual.strip():
        titles = [line.strip() for line in manual.splitlines() if line.strip()]
    active_index = int(round(to_number(src.get("listActiveIndex"), base["listActiveIndex"])))
    active_index = int(max(-1, min(200, active_index)))
    return {
        "enabled": to_boolean(src.get("enabled"), base["enabled"]),
        "contentMode": mode,
        "listStyle": list_style,
        "numberIndent": number_indent,
        "layout": layout,
        "manualTitles": titles,
        "listColor": normalize_color(src.get("listColor"), base["listColor"]),
        "listActiveColor": normalize_color(src.get("listActiveColor"), base["listActiveColor"]),
        "listActiveIndex": active_index,
        "stylePreset": _normalize_preset_key(src.get("stylePreset"), base["stylePreset"]),
        "style": normalize_text_style(src.get("style") or base["style"]),
    }


def _style_draft_keys(prefix: str, style: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}FontFamily": style["fontFamily"],
        f"{prefix}FontSize": style["fontSize"],
        f"{prefix}Bold": style["bold"],
        f"{prefix}Italic": style["italic"],
        f"{prefix}Color": style["color"],
        f"{prefix}FillMode": style["fillMode"],
        f"{prefix}GradientColors": list(style["gradientColors"]),
        f"{prefix}GradientDirection": style["gradientDirection"],
        f"{prefix}GlowColor": style["glowColor"],
        f"{prefix}GlowMode": style.get("glowMode", "solid"),
        f"{prefix}GlowGradientColors": list(style.get("glowGradientColors") or []),
        f"{prefix}GlowGradientDirection": style.get("glowGradientDirection", "horizontal"),
        f"{prefix}StrokeColor": style["strokeColor"],
        f"{prefix}StrokeWidth": style["strokeWidth"],
        f"{prefix}Shadow": style["shadow"],
        f"{prefix}ShadowBlur": style["shadowBlur"],
        f"{prefix}Glow": style["glow"],
        f"{prefix}GlowBlur": style["glowBlur"],
        f"{prefix}ExtrudeDepth": style["extrudeDepth"],
        f"{prefix}ExtrudeColor": style["extrudeColor"],
        f"{prefix}LetterSpacing": style["letterSpacing"],
        f"{prefix}LineSpacing": style["lineSpacing"],
        f"{prefix}BoxWidth": style.get("boxWidth", 0.0),
        f"{prefix}Align": style.get("align", "left"),
        f"{prefix}Anchor": style["anchor"],
        f"{prefix}X": style["x"],
        f"{prefix}Y": style["y"],
        f"{prefix}Opacity": style["opacity"],
    }


def _style_from_draft_keys(prefix: str, draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "fontFamily": draft.get(f"{prefix}FontFamily"),
        "fontSize": draft.get(f"{prefix}FontSize"),
        "bold": draft.get(f"{prefix}Bold"),
        "italic": draft.get(f"{prefix}Italic"),
        "color": draft.get(f"{prefix}Color"),
        "fillMode": draft.get(f"{prefix}FillMode"),
        "gradientColors": draft.get(f"{prefix}GradientColors"),
        "gradientDirection": draft.get(f"{prefix}GradientDirection"),
        "glowColor": draft.get(f"{prefix}GlowColor"),
        "glowMode": draft.get(f"{prefix}GlowMode"),
        "glowGradientColors": draft.get(f"{prefix}GlowGradientColors"),
        "glowGradientDirection": draft.get(f"{prefix}GlowGradientDirection"),
        "strokeColor": draft.get(f"{prefix}StrokeColor"),
        "strokeWidth": draft.get(f"{prefix}StrokeWidth"),
        "shadow": draft.get(f"{prefix}Shadow"),
        "shadowBlur": draft.get(f"{prefix}ShadowBlur"),
        "glow": draft.get(f"{prefix}Glow"),
        "glowBlur": draft.get(f"{prefix}GlowBlur"),
        "extrudeDepth": draft.get(f"{prefix}ExtrudeDepth"),
        "extrudeColor": draft.get(f"{prefix}ExtrudeColor"),
        "letterSpacing": draft.get(f"{prefix}LetterSpacing"),
        "lineSpacing": draft.get(f"{prefix}LineSpacing"),
        "boxWidth": draft.get(f"{prefix}BoxWidth"),
        "align": draft.get(f"{prefix}Align"),
        "anchor": draft.get(f"{prefix}Anchor"),
        "x": draft.get(f"{prefix}X"),
        "y": draft.get(f"{prefix}Y"),
        "opacity": draft.get(f"{prefix}Opacity"),
    }


def build_album_settings_state(template: dict[str, Any]) -> dict[str, Any]:
    settings = normalize_album_text_settings(template.get("albumText"))
    style = settings["style"]
    return {
        "albumEnabled": settings["enabled"],
        "albumContentMode": settings["contentMode"],
        "albumManualText": settings["manualText"],
        "albumStylePreset": settings["stylePreset"],
        **_style_draft_keys("album", style),
    }


def build_title_settings_state(template: dict[str, Any]) -> dict[str, Any]:
    settings = normalize_title_text_settings(template.get("titleText"))
    style = settings["style"]
    return {
        "titleEnabled": settings["enabled"],
        "titleContentMode": settings["contentMode"],
        "titleListStyle": settings["listStyle"],
        "titleNumberIndent": settings["numberIndent"],
        "titleLayout": settings["layout"],
        "titleManualTitles": list(settings["manualTitles"]),
        "titleListColor": settings["listColor"],
        "titleListActiveColor": settings["listActiveColor"],
        "titleListActiveIndex": settings["listActiveIndex"],
        "titleStylePreset": settings["stylePreset"],
        **_style_draft_keys("title", style),
    }


def album_settings_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    return normalize_album_text_settings(
        {
            "enabled": draft.get("albumEnabled", False),
            "contentMode": draft.get("albumContentMode", "pipeline"),
            "manualText": draft.get("albumManualText", ""),
            "stylePreset": draft.get("albumStylePreset", "neon_glow"),
            "style": _style_from_draft_keys("album", draft),
        }
    )


def title_settings_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    return normalize_title_text_settings(
        {
            "enabled": draft.get("titleEnabled", False),
            "contentMode": draft.get("titleContentMode", "pipeline"),
            "listStyle": draft.get("titleListStyle", "number"),
            "numberIndent": draft.get("titleNumberIndent", "aligned"),
            "layout": draft.get("titleLayout", "column"),
            "manualTitles": draft.get("titleManualTitles", []),
            "listColor": draft.get("titleListColor"),
            "listActiveColor": draft.get("titleListActiveColor"),
            "listActiveIndex": draft.get("titleListActiveIndex"),
            "stylePreset": draft.get("titleStylePreset", "midnight_stack"),
            "style": _style_from_draft_keys("title", draft),
        }
    )


def is_builtin_text_domain_preset(preset_key: str | None) -> bool:
    return _canonical_preset_id(preset_key) in _BUILTIN_IDS


def build_text_domain_preset_factory_style(preset_id: str) -> dict[str, Any] | None:
    key = _canonical_preset_id(preset_id)
    patch = TEXT_DOMAIN_PRESET_PATCHES.get(key)
    return dict(patch) if patch else None


def resolve_text_domain_preset_style(domain: str, preset_id: str) -> dict[str, Any] | None:
    key = _canonical_preset_id(preset_id)
    if key not in _BUILTIN_IDS:
        return None
    override = get_domain_preset_override(domain, key)
    if isinstance(override, dict) and override:
        return normalize_text_style({**(_DEFAULT_STYLE), **override})
    factory = build_text_domain_preset_factory_style(key)
    return normalize_text_style(factory) if factory else None


def capture_text_domain_preset(domain: str, preset_id: str, style: dict[str, Any]) -> None:
    key = _canonical_preset_id(preset_id)
    if key not in _BUILTIN_IDS:
        return
    save_domain_preset_override(domain, key, normalize_text_style(style))


def restore_text_domain_preset(domain: str, preset_id: str) -> dict[str, Any] | None:
    key = _canonical_preset_id(preset_id)
    if key not in _BUILTIN_IDS:
        return None
    clear_domain_preset_override(domain, key)
    return resolve_text_domain_preset_style(domain, key)


def text_domain_preset_has_override(domain: str, preset_id: str) -> bool:
    return has_domain_preset_override(domain, _canonical_preset_id(preset_id))


def style_patch_for_domain(domain: str, style: dict[str, Any]) -> dict[str, Any]:
    """Map a style dict onto album* or title* draft keys."""
    prefix = "album" if domain == "album" else "title"
    return _style_draft_keys(prefix, normalize_text_style(style))


def draft_style_snapshot(domain: str, draft: dict[str, Any]) -> dict[str, Any]:
    prefix = "album" if domain == "album" else "title"
    return normalize_text_style(_style_from_draft_keys(prefix, draft))
