"""Per track-list sub-template style snapshots (Minimal White, Forest Mist, …)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from studio.core.playlist_settings import PlaylistSettings, PlaylistTypography
from studio.core.playlist_style import apply_style_to_settings
from studio.core.playlist_sub_templates import SUB_TEMPLATES_BY_ID
from studio.core.playlist_row_chrome import (
    PlaylistRowChrome,
    default_row_chrome_for_layout,
    row_chrome_from_legacy,
    sync_legacy_row_flags,
)

DEFAULT_LIST_ROW_GAP = 6


def capture_style_dict(settings: PlaylistSettings) -> dict[str, Any]:
    sync_legacy_row_flags(settings)
    return {
        "colors": dict(settings.colors),
        "typography": settings.typography.to_dict(),
        "corner_radius": settings.corner_radius,
        "list_row_gap": settings.list_row_gap,
        "color_filter_id": settings.color_filter_id,
        "show_track_numbers": settings.show_track_numbers,
        "show_durations": settings.show_durations,
        "row_chrome": settings.row_chrome.to_dict(),
        "component_layout": {k: dict(v) for k, v in settings.component_layout.items()},
        "background_path": settings.background_path,
    }


def _resolve_row_chrome(data: dict[str, Any], sub_template_id: str) -> PlaylistRowChrome:
    raw = data.get("row_chrome")
    if isinstance(raw, dict) and raw:
        return PlaylistRowChrome.from_dict(raw)
    sub = SUB_TEMPLATES_BY_ID.get(sub_template_id)
    layout_style = sub.layout_style if sub else "standard"
    chrome = default_row_chrome_for_layout(layout_style)
    legacy = row_chrome_from_legacy(
        show_track_numbers=bool(data.get("show_track_numbers", True)),
        show_durations=bool(data.get("show_durations", True)),
    )
    chrome.numbers.enabled = legacy.numbers.enabled
    chrome.duration.enabled = legacy.duration.enabled
    return chrome


def apply_style_dict(settings: PlaylistSettings, data: dict[str, Any]) -> None:
    settings.colors = dict(data.get("colors") or {})
    settings.typography = PlaylistTypography.from_dict(data.get("typography") or {})
    settings.corner_radius = int(data.get("corner_radius", settings.corner_radius))
    settings.list_row_gap = int(data.get("list_row_gap", DEFAULT_LIST_ROW_GAP))
    settings.color_filter_id = str(data.get("color_filter_id") or "original")
    settings.row_chrome = _resolve_row_chrome(data, settings.sub_template_id or "glass-blur")
    sync_legacy_row_flags(settings)
    settings.component_layout = {
        k: {kk: float(vv) for kk, vv in v.items()}
        for k, v in (data.get("component_layout") or {}).items()
    }
    bg = data.get("background_path")
    settings.background_path = str(bg) if bg else None


def default_style_dict(sub_template_id: str) -> dict[str, Any]:
    sub = SUB_TEMPLATES_BY_ID.get(sub_template_id)
    if sub is None:
        return capture_style_dict(PlaylistSettings(sub_template_id=sub_template_id))

    seed = PlaylistSettings(
        sub_template_id=sub_template_id,
        color_filter_id="original",
        corner_radius=sub.corner_radius,
        list_row_gap=DEFAULT_LIST_ROW_GAP,
    )
    apply_style_to_settings(seed)
    if sub.layout_style in ("minimal_white", "forest_mist", "emotional_music"):
        seed.typography.song_title_size = 13
        seed.typography.song_meta_size = 11
        seed.row_chrome = default_row_chrome_for_layout(sub.layout_style)
        sync_legacy_row_flags(seed)
    return capture_style_dict(seed)


def migrate_legacy_flat_style(settings: PlaylistSettings) -> None:
    """Copy the legacy single-bucket style into the active sub-template slot once."""
    if settings.styles_by_sub_template:
        return
    sub_id = settings.sub_template_id or "glass-blur"
    settings.styles_by_sub_template[sub_id] = capture_style_dict(settings)


def switch_sub_template(settings: PlaylistSettings, new_sub_template_id: str) -> None:
    if new_sub_template_id not in SUB_TEMPLATES_BY_ID:
        return
    migrate_legacy_flat_style(settings)
    current_id = settings.sub_template_id or "glass-blur"
    if current_id == new_sub_template_id:
        return

    settings.styles_by_sub_template[current_id] = capture_style_dict(settings)
    settings.sub_template_id = new_sub_template_id

    saved = settings.styles_by_sub_template.get(new_sub_template_id)
    if saved:
        apply_style_dict(settings, saved)
    else:
        apply_style_dict(settings, default_style_dict(new_sub_template_id))


def reset_row_chrome_to_default(settings: PlaylistSettings) -> None:
    sub = SUB_TEMPLATES_BY_ID.get(settings.sub_template_id or "glass-blur")
    layout_style = sub.layout_style if sub else "standard"
    settings.row_chrome = default_row_chrome_for_layout(layout_style)
    sync_legacy_row_flags(settings)


def reset_sub_template_style(settings: PlaylistSettings) -> None:
    migrate_legacy_flat_style(settings)
    sub_id = settings.sub_template_id or "glass-blur"
    default = default_style_dict(sub_id)
    settings.styles_by_sub_template[sub_id] = deepcopy(default)
    apply_style_dict(settings, default)


def flush_active_style_to_store(settings: PlaylistSettings) -> dict[str, dict[str, Any]]:
    migrate_legacy_flat_style(settings)
    store = {k: deepcopy(v) for k, v in settings.styles_by_sub_template.items()}
    sub_id = settings.sub_template_id or "glass-blur"
    store[sub_id] = capture_style_dict(settings)
    return store
