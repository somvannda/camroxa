"""Shared metadata for filters and visualizer styles.

Small, UI-facing descriptors (id, display name, swatch gradient) used by the
Inspector/Effects/Visualizer tabs now; the filters phase and visualizer phase
implement the actual pixel/paint logic against the same ids so nothing here
needs to change later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterInfo:
    id: str
    name: str
    swatch_from: str
    swatch_to: str


@dataclass(frozen=True)
class VizStyleInfo:
    id: str
    name: str
    swatch_from: str
    swatch_to: str


FILTERS: list[FilterInfo] = [
    FilterInfo("none", "Original", "#666666", "#999999"),
    FilterInfo("vivid", "Vivid", "#ff5470", "#ffb648"),
    FilterInfo("noir", "Noir", "#333333", "#111111"),
    FilterInfo("warm", "Warm", "#ffb648", "#e6712e"),
    FilterInfo("cool", "Cool", "#5cc9ff", "#7c5cff"),
    FilterInfo("fade", "Faded", "#c9c9d4", "#9a9aab"),
    FilterInfo("dream", "Dream", "#ff9ad5", "#7c5cff"),
    FilterInfo("mono-blue", "Cyberblue", "#0a1a3a", "#2f6fff"),
    FilterInfo("sepia", "Sepia", "#8b6914", "#d4a574"),
    FilterInfo("vintage", "Vintage", "#c4a882", "#8b7355"),
    FilterInfo("punch", "Punch", "#ff3366", "#ff9933"),
    FilterInfo("emerald", "Emerald", "#0d9488", "#34d399"),
    FilterInfo("rose", "Rose", "#f472b6", "#fb7185"),
    FilterInfo("golden", "Golden", "#fbbf24", "#f59e0b"),
    FilterInfo("arctic", "Arctic", "#e0f2fe", "#7dd3fc"),
    FilterInfo("sunset", "Sunset", "#f97316", "#ec4899"),
    FilterInfo("neon", "Neon", "#22d3ee", "#a855f7"),
    FilterInfo("matte", "Matte", "#78716c", "#a8a29e"),
    FilterInfo("bleach", "Bleach", "#fafafa", "#e5e5e5"),
    FilterInfo("charcoal", "Charcoal", "#404040", "#262626"),
    FilterInfo("lavender", "Lavender", "#c4b5fd", "#a78bfa"),
    FilterInfo("citrus", "Citrus", "#a3e635", "#facc15"),
    FilterInfo("crimson", "Crimson", "#991b1b", "#dc2626"),
    FilterInfo("teal", "Teal", "#115e59", "#14b8a6"),
    FilterInfo("silver", "Silver", "#d4d4d8", "#a1a1aa"),
    FilterInfo("ink", "Ink", "#1e1b4b", "#312e81"),
    FilterInfo("copper", "Copper", "#b45309", "#ea580c"),
    FilterInfo("mist", "Mist", "#cbd5e1", "#94a3b8"),
]

VIZ_STYLES: list[VizStyleInfo] = [
    VizStyleInfo("bars", "Bars", "#7c5cff", "#26d6a4"),
    VizStyleInfo("mirror-bars", "Mirror Bars", "#ff5470", "#ffb648"),
    VizStyleInfo("wave", "Waveform", "#26d6a4", "#5cc9ff"),
    VizStyleInfo("circle", "Radial", "#ffb648", "#ff5470"),
]

FILTERS_BY_ID = {f.id: f for f in FILTERS}
VIZ_STYLES_BY_ID = {v.id: v for v in VIZ_STYLES}

TEXT_PRESETS_UI: list[tuple[str, str, str]] = [
    ("title", "Big Title", "h1"),
    ("subtitle", "Subtitle text", "h2"),
    ("caption", "Caption / lower-third", "h3"),
]
