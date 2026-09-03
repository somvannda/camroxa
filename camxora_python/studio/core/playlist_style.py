"""Resolve final playlist colors from sub-template + color filter."""

from __future__ import annotations

from studio.core.playlist_color_filters import COLOR_FILTERS_BY_ID
from studio.core.playlist_palette import PALETTE_SLOT_COUNT, expand_forest_mist_palette, expand_palette
from studio.core.playlist_settings import PlaylistSettings
from studio.core.playlist_sub_templates import DEFAULT_SUB_FOR_TEMPLATE, SUB_TEMPLATES_BY_ID


def default_sub_template_for(template_id: str) -> str:
    return DEFAULT_SUB_FOR_TEMPLATE.get(template_id, "glass-blur")


def resolve_playlist_colors(settings: PlaylistSettings) -> dict[str, str]:
    if settings.color_filter_id == "custom" and settings.colors:
        return dict(settings.colors)

    sub_id = settings.sub_template_id or default_sub_template_for(settings.template_id)
    sub = SUB_TEMPLATES_BY_ID.get(sub_id)
    merged = dict(sub.colors) if sub is not None else {}

    filt = COLOR_FILTERS_BY_ID.get(settings.color_filter_id or "original")
    filt_colors: dict[str, str] = filt.colors if filt is not None else {}
    if filt is not None and sub is not None:
        if sub.layout_style == "forest_mist":
            if settings.color_filter_id == "original":
                merged = dict(sub.colors)
            else:
                merged = expand_forest_mist_palette(*filt.palette)
                merged.update(filt_colors)
        elif sub.layout_style == "minimal_white":
            merged = expand_palette(*filt.palette)
            merged.update(filt_colors)

    accent = merged.get("accent")
    uses_palette = sub is not None and sub.layout_style in ("minimal_white", "forest_mist")
    if accent and "selected_row" not in filt_colors and not uses_palette:
        merged.setdefault("selected_row", _tint_hex(accent, alpha=0.18))
    if accent and "active_glow" not in filt_colors and not uses_palette:
        merged.setdefault("active_glow", _tint_hex(accent, alpha=0.28))

    if sub is not None and sub.layout_style == "forest_mist":
        merged["play_icon"] = merged.get("accent", merged.get("text", "#a2d149"))

    return merged


def palette_slot_count() -> int:
    """Number of user-facing colors on a Minimal White palette chip."""
    return PALETTE_SLOT_COUNT


def _tint_hex(hex_color: str, *, alpha: float) -> str:
    raw = hex_color.lstrip("#")
    if len(raw) >= 6:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        a = max(0, min(255, int(alpha * 255)))
        return f"#{r:02x}{g:02x}{b:02x}{a:02x}"
    return hex_color


def apply_style_to_settings(settings: PlaylistSettings) -> None:
    settings.sub_template_id = settings.sub_template_id or default_sub_template_for(settings.template_id)
    if not settings.color_filter_id:
        settings.color_filter_id = "original"
    sub = SUB_TEMPLATES_BY_ID.get(settings.sub_template_id)
    if sub is not None:
        if sub.layout_style in ("minimal_white", "forest_mist"):
            settings.typography.song_title_size = 13
            settings.typography.song_meta_size = 11
    if settings.color_filter_id == "custom":
        if sub is not None and sub.layout_style in ("minimal_white", "forest_mist"):
            from core.playlist_palette import expand_forest_mist_palette, expand_palette, palette_from_colors

            palette = palette_from_colors(settings.colors)
            if sub.layout_style == "forest_mist":
                settings.colors = expand_forest_mist_palette(*palette)
            else:
                settings.colors = expand_palette(*palette)
        return
    settings.colors = resolve_playlist_colors(settings)
