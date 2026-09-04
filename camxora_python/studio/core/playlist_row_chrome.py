"""Track row chrome — numbers, play icon, duration, playing animation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ROW_INSET_X = 6
DEFAULT_NUM_COLUMN_W = 30

PLAY_WHEN_PLAYING = ("play_icon", "animation", "both", "hide")
PLAY_SHAPES = ("circle", "square", "none")
PLAY_PLACEMENTS = ("leading", "trailing")
DURATION_PLACEMENTS = ("trailing", "before_animation")
ANIMATION_PLACEMENTS = ("trailing", "leading")
NUMBER_FORMATS = ("padded2", "plain")


@dataclass
class RowNumberStyle:
    enabled: bool = True
    format: str = "padded2"
    column_width_px: int = DEFAULT_NUM_COLUMN_W
    color: str = ""
    active_color: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "format": self.format,
            "column_width_px": self.column_width_px,
            "color": self.color,
            "active_color": self.active_color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RowNumberStyle:
        data = data or {}
        fmt = str(data.get("format", "padded2"))
        if fmt not in NUMBER_FORMATS:
            fmt = "padded2"
        return cls(
            enabled=bool(data.get("enabled", True)),
            format=fmt,
            column_width_px=max(16, int(data.get("column_width_px", DEFAULT_NUM_COLUMN_W))),
            color=str(data.get("color") or ""),
            active_color=str(data.get("active_color") or ""),
        )


@dataclass
class RowPlayStyle:
    enabled: bool = True
    show_on_inactive: bool = False
    when_playing: str = "play_icon"
    shape: str = "circle"
    size_scale_pct: int = 100
    fill_color: str = ""
    icon_color: str = ""
    placement: str = "leading"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "show_on_inactive": self.show_on_inactive,
            "when_playing": self.when_playing,
            "shape": self.shape,
            "size_scale_pct": self.size_scale_pct,
            "fill_color": self.fill_color,
            "icon_color": self.icon_color,
            "placement": self.placement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RowPlayStyle:
        data = data or {}
        when = str(data.get("when_playing", "play_icon"))
        if when not in PLAY_WHEN_PLAYING:
            when = "play_icon"
        shape = str(data.get("shape", "circle"))
        if shape not in PLAY_SHAPES:
            shape = "circle"
        placement = str(data.get("placement", "leading"))
        if placement not in PLAY_PLACEMENTS:
            placement = "leading"
        return cls(
            enabled=bool(data.get("enabled", True)),
            show_on_inactive=bool(data.get("show_on_inactive", False)),
            when_playing=when,
            shape=shape,
            size_scale_pct=max(50, min(160, int(data.get("size_scale_pct", 100)))),
            fill_color=str(data.get("fill_color") or ""),
            icon_color=str(data.get("icon_color") or ""),
            placement=placement,
        )


@dataclass
class RowDurationStyle:
    enabled: bool = True
    placement: str = "trailing"
    color: str = ""
    active_color: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "placement": self.placement,
            "color": self.color,
            "active_color": self.active_color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RowDurationStyle:
        data = data or {}
        placement = str(data.get("placement", "trailing"))
        if placement not in DURATION_PLACEMENTS:
            placement = "trailing"
        return cls(
            enabled=bool(data.get("enabled", True)),
            placement=placement,
            color=str(data.get("color") or ""),
            active_color=str(data.get("active_color") or ""),
        )


@dataclass
class RowAnimationStyle:
    enabled: bool = True
    style: str = "bars"
    bar_count: int = 4
    bar_width_px: int = 2
    bar_gap_px: int = 2
    height_px: int = 14
    color: str = ""
    active_color: str = ""
    placement: str = "trailing"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "style": self.style,
            "bar_count": self.bar_count,
            "bar_width_px": self.bar_width_px,
            "bar_gap_px": self.bar_gap_px,
            "height_px": self.height_px,
            "color": self.color,
            "active_color": self.active_color,
            "placement": self.placement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RowAnimationStyle:
        data = data or {}
        placement = str(data.get("placement", "trailing"))
        if placement not in ANIMATION_PLACEMENTS:
            placement = "trailing"
        return cls(
            enabled=bool(data.get("enabled", True)),
            style=str(data.get("style") or "bars"),
            bar_count=max(2, min(8, int(data.get("bar_count", 4)))),
            bar_width_px=max(1, min(6, int(data.get("bar_width_px", 2)))),
            bar_gap_px=max(1, min(8, int(data.get("bar_gap_px", 2)))),
            height_px=max(8, min(24, int(data.get("height_px", 14)))),
            color=str(data.get("color") or ""),
            active_color=str(data.get("active_color") or ""),
            placement=placement,
        )


@dataclass
class PlaylistRowChrome:
    numbers: RowNumberStyle = field(default_factory=RowNumberStyle)
    play: RowPlayStyle = field(default_factory=RowPlayStyle)
    duration: RowDurationStyle = field(default_factory=RowDurationStyle)
    animation: RowAnimationStyle = field(default_factory=RowAnimationStyle)

    def to_dict(self) -> dict[str, Any]:
        return {
            "numbers": self.numbers.to_dict(),
            "play": self.play.to_dict(),
            "duration": self.duration.to_dict(),
            "animation": self.animation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PlaylistRowChrome:
        data = data or {}
        return cls(
            numbers=RowNumberStyle.from_dict(data.get("numbers")),
            play=RowPlayStyle.from_dict(data.get("play")),
            duration=RowDurationStyle.from_dict(data.get("duration")),
            animation=RowAnimationStyle.from_dict(data.get("animation")),
        )


def format_track_number(index: int, fmt: str) -> str:
    n = index + 1
    if fmt == "plain":
        return str(n)
    return f"{n:02d}"


def default_row_chrome_for_layout(layout_style: str) -> PlaylistRowChrome:
    if layout_style == "forest_mist":
        return PlaylistRowChrome(
            numbers=RowNumberStyle(enabled=True),
            play=RowPlayStyle(
                enabled=True,
                show_on_inactive=False,
                when_playing="play_icon",
                placement="leading",
            ),
            duration=RowDurationStyle(enabled=True, placement="trailing"),
            animation=RowAnimationStyle(
                enabled=True,
                placement="trailing",
                bar_count=4,
                bar_width_px=2,
                bar_gap_px=2,
                height_px=14,
            ),
        )
    if layout_style == "minimal_white":
        return PlaylistRowChrome(
            numbers=RowNumberStyle(enabled=True),
            play=RowPlayStyle(
                enabled=True,
                show_on_inactive=True,
                when_playing="animation",
                placement="leading",
            ),
            duration=RowDurationStyle(enabled=True, placement="trailing"),
            animation=RowAnimationStyle(
                enabled=True,
                placement="leading",
                bar_count=4,
                bar_width_px=2,
                bar_gap_px=2,
                height_px=14,
            ),
        )
    if layout_style == "emotional_music":
        # Read-only scene view. Active row: leading play icon (replaces the
        # number) + trailing animated equalizer bars; inactive rows just show
        # number/title/artist/duration with no affordances.
        return PlaylistRowChrome(
            numbers=RowNumberStyle(enabled=True),
            play=RowPlayStyle(
                enabled=True,
                show_on_inactive=False,
                when_playing="play_icon",
                placement="leading",
            ),
            duration=RowDurationStyle(enabled=True, placement="trailing"),
            animation=RowAnimationStyle(
                enabled=True,
                placement="trailing",
                bar_count=4,
                bar_width_px=2,
                bar_gap_px=2,
                height_px=13,
            ),
        )
    return PlaylistRowChrome()


def row_chrome_from_legacy(*, show_track_numbers: bool, show_durations: bool) -> PlaylistRowChrome:
    chrome = PlaylistRowChrome()
    chrome.numbers.enabled = show_track_numbers
    chrome.duration.enabled = show_durations
    return chrome


def sync_legacy_row_flags(settings) -> None:
    """Keep legacy booleans aligned with row chrome for older code paths."""
    settings.show_track_numbers = settings.row_chrome.numbers.enabled
    settings.show_durations = settings.row_chrome.duration.enabled
