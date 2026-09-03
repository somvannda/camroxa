"""Playlist template configuration — persisted on Project."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from studio.core.playlist_row_chrome import PlaylistRowChrome, sync_legacy_row_flags

# Ordered visual blocks the user can reorder in the Playlist editor.
PLAYLIST_COMPONENTS: tuple[str, ...] = (
    "cover",
    "now_playing",
    "song_list",
    "waveform",
    "progress",
    "title",
)

COMPONENT_LABELS: dict[str, str] = {
    "cover": "Album cover",
    "now_playing": "Now playing",
    "song_list": "Song list",
    "waveform": "Waveform",
    "progress": "Progress bar",
    "title": "Album title",
}


def default_component_order() -> list[str]:
    return list(PLAYLIST_COMPONENTS)


@dataclass
class PlaylistTypography:
    font_family: str = "Segoe UI"
    album_title_size: int = 28
    song_title_size: int = 15
    song_meta_size: int = 12
    now_playing_size: int = 18
    song_title_variant: str = "normal"
    song_meta_variant: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "font_family": self.font_family,
            "album_title_size": self.album_title_size,
            "song_title_size": self.song_title_size,
            "song_meta_size": self.song_meta_size,
            "now_playing_size": self.now_playing_size,
            "song_title_variant": self.song_title_variant,
            "song_meta_variant": self.song_meta_variant,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlaylistTypography":
        return cls(
            font_family=str(data.get("font_family", "Segoe UI")),
            album_title_size=int(data.get("album_title_size", 28)),
            song_title_size=int(data.get("song_title_size", 15)),
            song_meta_size=int(data.get("song_meta_size", 12)),
            now_playing_size=int(data.get("now_playing_size", 18)),
            song_title_variant=str(data.get("song_title_variant", "normal")),
            song_meta_variant=str(data.get("song_meta_variant", "normal")),
        )


@dataclass
class PlaylistSettings:
    template_id: str = "glass-romance"
    album_title: str = ""
    cover_path: str | None = None
    background_path: str | None = None
    song_ids: list[str] = field(default_factory=list)
    component_order: list[str] = field(default_factory=default_component_order)
    colors: dict[str, str] = field(default_factory=dict)
    typography: PlaylistTypography = field(default_factory=PlaylistTypography)
    cover_size_pct: int = 38
    list_side: str = "right"  # "left" | "right"
    show_track_numbers: bool = True
    show_durations: bool = True
    row_chrome: PlaylistRowChrome = field(default_factory=PlaylistRowChrome)
    corner_radius: int = 12
    list_row_gap: int = 6
    component_layout: dict[str, dict[str, float]] = field(default_factory=dict)
    selected_component: str | None = None
    sub_template_id: str = "glass-blur"
    color_filter_id: str = "original"
    styles_by_sub_template: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from core.playlist_sub_template_styles import flush_active_style_to_store

        return {
            "template_id": self.template_id,
            "album_title": self.album_title,
            "cover_path": self.cover_path,
            "background_path": self.background_path,
            "song_ids": list(self.song_ids),
            "component_order": list(self.component_order),
            "colors": dict(self.colors),
            "typography": self.typography.to_dict(),
            "cover_size_pct": self.cover_size_pct,
            "list_side": self.list_side,
            "show_track_numbers": self.show_track_numbers,
            "show_durations": self.show_durations,
            "row_chrome": self.row_chrome.to_dict(),
            "corner_radius": self.corner_radius,
            "list_row_gap": self.list_row_gap,
            "component_layout": {k: dict(v) for k, v in self.component_layout.items()},
            "selected_component": self.selected_component,
            "sub_template_id": self.sub_template_id,
            "color_filter_id": self.color_filter_id,
            "styles_by_sub_template": flush_active_style_to_store(self),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlaylistSettings":
        from core.playlist_sub_template_styles import apply_style_dict, migrate_legacy_flat_style

        settings = cls(
            template_id=str(data.get("template_id", "glass-romance")),
            album_title=str(data.get("album_title", "")),
            cover_path=data.get("cover_path"),
            background_path=data.get("background_path"),
            song_ids=list(data.get("song_ids", [])),
            component_order=list(data.get("component_order") or default_component_order()),
            colors=dict(data.get("colors", {})),
            typography=PlaylistTypography.from_dict(data.get("typography", {})),
            cover_size_pct=int(data.get("cover_size_pct", 38)),
            list_side=str(data.get("list_side", "right")),
            show_track_numbers=bool(data.get("show_track_numbers", True)),
            show_durations=bool(data.get("show_durations", True)),
            row_chrome=PlaylistRowChrome.from_dict(data.get("row_chrome")),
            corner_radius=int(data.get("corner_radius", 12)),
            list_row_gap=int(data.get("list_row_gap", 6)),
            component_layout={
                k: {kk: float(vv) for kk, vv in v.items()}
                for k, v in (data.get("component_layout") or {}).items()
            },
            selected_component=data.get("selected_component"),
            sub_template_id=str(data.get("sub_template_id", "glass-blur")),
            color_filter_id=str(data.get("color_filter_id", "original")),
            styles_by_sub_template={
                str(k): dict(v) if isinstance(v, dict) else {}
                for k, v in (data.get("styles_by_sub_template") or {}).items()
            },
        )
        migrate_legacy_flat_style(settings)
        stored = settings.styles_by_sub_template.get(settings.sub_template_id)
        if stored:
            apply_style_dict(settings, stored)
        else:
            sync_legacy_row_flags(settings)
        return settings
