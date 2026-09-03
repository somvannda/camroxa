"""24 five-color palettes for Minimal White + accent overrides for other styles."""

from __future__ import annotations

from dataclasses import dataclass

from studio.core.playlist_palette import PALETTE_SLOT_COUNT, Palette5

# (background, surface, text, muted, selected_row)
_PLAYLIST_PALETTES: dict[str, Palette5] = {
    "original": ("#e8eaee", "#ffffff", "#000000", "#8e8e93", "#f2f2f7"),
    "violet-dream": ("#ece8ff", "#faf8ff", "#2e1065", "#8b7cb8", "#ede9fe"),
    "rose-gold": ("#fde8f0", "#fffafb", "#4a1d35", "#b07a96", "#fce7f3"),
    "sunset": ("#ffedd5", "#fffbf5", "#431407", "#c2785a", "#ffedd5"),
    "golden": ("#fef9c3", "#fffef0", "#422006", "#a8945a", "#fef08a"),
    "lime-fresh": ("#ecfccb", "#f7fee7", "#1a2e05", "#6b8f4a", "#d9f99d"),
    "mint": ("#ccfbf1", "#f0fdfa", "#134e4a", "#5f9e8f", "#99f6e4"),
    "ocean": ("#dbeafe", "#f0f9ff", "#0c4a6e", "#5b8fa8", "#bae6fd"),
    "arctic": ("#cffafe", "#ecfeff", "#164e63", "#5f9aaa", "#a5f3fc"),
    "sky": ("#e0f2fe", "#f0f9ff", "#0c4a6e", "#64748b", "#bae6fd"),
    "indigo": ("#e0e7ff", "#eef2ff", "#312e81", "#6366a8", "#c7d2fe"),
    "purple-haze": ("#f3e8ff", "#faf5ff", "#581c87", "#9f7aba", "#e9d5ff"),
    "magenta": ("#fae8ff", "#fdf4ff", "#701a75", "#b565b5", "#f5d0fe"),
    "crimson": ("#fee2e2", "#fff5f5", "#7f1d1d", "#b05a5a", "#fecaca"),
    "coral": ("#ffe4e6", "#fff1f2", "#881337", "#c07080", "#fecdd3"),
    "peach": ("#ffedd5", "#fffaf5", "#7c2d12", "#c8936a", "#fed7aa"),
    "sand": ("#f5f5f4", "#fafaf9", "#292524", "#78716c", "#e7e5e4"),
    "slate": ("#e2e8f0", "#f8fafc", "#0f172a", "#64748b", "#cbd5e1"),
    "steel": ("#cbd5e1", "#f1f5f9", "#0f172a", "#475569", "#94a3b8"),
    "neon-green": ("#dcfce7", "#f0fdf4", "#14532d", "#4ade80", "#bbf7d0"),
    "neon-cyan": ("#cffafe", "#ecfeff", "#164e63", "#22d3ee", "#a5f3fc"),
    "neon-pink": ("#fce7f3", "#fdf2f8", "#831843", "#f472b6", "#fbcfe8"),
    "mono-light": ("#f4f4f5", "#ffffff", "#18181b", "#71717a", "#e4e4e7"),
    "mono-dark": ("#18181b", "#27272a", "#fafafa", "#a1a1aa", "#3f3f46"),
}


@dataclass(frozen=True, slots=True)
class PlaylistColorFilter:
    id: str
    name: str
    swatch: str
    palette: Palette5
    colors: dict[str, str]


def _filter(filter_id: str, name: str, palette: Palette5, *, colors: dict[str, str] | None = None) -> PlaylistColorFilter:
    """Build a filter; ``swatch`` previews the active-row slot."""
    return PlaylistColorFilter(
        id=filter_id,
        name=name,
        swatch=palette[4],
        palette=palette,
        colors=colors or {},
    )


PLAYLIST_COLOR_FILTERS: tuple[PlaylistColorFilter, ...] = tuple(
    _filter(fid, name, _PLAYLIST_PALETTES[fid], colors=extra)
    for fid, name, extra in (
        ("original", "Original", {}),
        ("violet-dream", "Violet Dream", {"accent": "#8b5cf6", "accent2": "#c084fc"}),
        ("rose-gold", "Rose Gold", {"accent": "#f472b6", "accent2": "#fb7185"}),
        ("sunset", "Sunset", {"accent": "#f97316", "accent2": "#fb923c"}),
        ("golden", "Golden", {"accent": "#eab308", "accent2": "#facc15"}),
        ("lime-fresh", "Lime Fresh", {"accent": "#84cc16", "accent2": "#a3e635"}),
        ("mint", "Mint", {"accent": "#2dd4bf", "accent2": "#5eead4"}),
        ("ocean", "Ocean", {"accent": "#0ea5e9", "accent2": "#38bdf8"}),
        ("arctic", "Arctic", {"accent": "#67e8f9", "accent2": "#a5f3fc"}),
        ("sky", "Sky", {"accent": "#60a5fa", "accent2": "#93c5fd"}),
        ("indigo", "Indigo", {"accent": "#6366f1", "accent2": "#818cf8"}),
        ("purple-haze", "Purple Haze", {"accent": "#a855f7", "accent2": "#c084fc"}),
        ("magenta", "Magenta", {"accent": "#d946ef", "accent2": "#e879f9"}),
        ("crimson", "Crimson", {"accent": "#ef4444", "accent2": "#f87171"}),
        ("coral", "Coral", {"accent": "#fb7185", "accent2": "#fda4af"}),
        ("peach", "Peach", {"accent": "#fdba74", "accent2": "#fed7aa"}),
        ("sand", "Sand", {"accent": "#78716c", "accent2": "#a8a29e"}),
        ("slate", "Slate", {"accent": "#64748b", "accent2": "#94a3b8"}),
        ("steel", "Steel", {"accent": "#475569", "accent2": "#64748b"}),
        ("neon-green", "Neon Green", {"accent": "#22c55e", "accent2": "#4ade80"}),
        ("neon-cyan", "Neon Cyan", {"accent": "#06b6d4", "accent2": "#22d3ee"}),
        ("neon-pink", "Neon Pink", {"accent": "#ec4899", "accent2": "#f472b6"}),
        ("mono-light", "Mono Light", {}),
        ("mono-dark", "Mono Dark", {}),
    )
)

COLOR_FILTERS_BY_ID: dict[str, PlaylistColorFilter] = {f.id: f for f in PLAYLIST_COLOR_FILTERS}

assert len(PLAYLIST_COLOR_FILTERS) == 24
assert all(len(f.palette) == PALETTE_SLOT_COUNT for f in PLAYLIST_COLOR_FILTERS)
