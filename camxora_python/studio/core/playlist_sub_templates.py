"""Track-list sub-templates — 10 layout styles (reference track-list cards)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlaylistSubTemplate:
    id: str
    name: str
    colors: dict[str, str]
    corner_radius: int = 14
    glass: bool = False
    neon_border: bool = False
    layout_style: str = "standard"  # "minimal_white" | "forest_mist" | "standard"


def _c(
    bg_from: str,
    bg_to: str,
    surface: str,
    text: str,
    muted: str,
    accent: str,
    accent2: str,
    selected_row: str,
) -> dict[str, str]:
    return {
        "bg_from": bg_from,
        "bg_to": bg_to,
        "surface": surface,
        "text": text,
        "muted": muted,
        "accent": accent,
        "accent2": accent2,
        "selected_row": selected_row,
    }


PLAYLIST_SUB_TEMPLATES: tuple[PlaylistSubTemplate, ...] = (
    PlaylistSubTemplate(
        "minimal-white",
        "Minimal White",
        {
            "bg_from": "#e8eaee",
            "bg_to": "#f5f6f8",
            "surface": "#ffffff",
            "text": "#000000",
            "muted": "#8e8e93",
            "accent": "#6b6bff",
            "accent2": "#8b8bff",
            "active_text": "#6b6bff",
            "selected_row": "#f2f2f7",
            "button_inactive": "#ececef",
            "button_active": "#ffffff",
            "active_glow": "#6464ff40",
            "icon": "#aeaeb2",
            "card_shadow": "#00000045",
            "divider": "#e5e5ea",
        },
        corner_radius=28,
        layout_style="minimal_white",
    ),
    PlaylistSubTemplate(
        "forest-mist",
        "Forest Mist",
        {
            "bg_from": "#0f1812",
            "bg_to": "#050a08",
            "surface": "#0a120a28",
            "frame_border": "#a2d14966",
            "text": "#ffffff",
            "muted": "#8a9a8a",
            "accent": "#a2d149",
            "accent2": "#86efac",
            "active_text": "#a2d149",
            "selected_row": "#1a3d2a66",
            "button_inactive": "#0f2218",
            "play_icon": "#a2d149",
            "divider": "#ffffff22",
            "card_shadow": "#00000045",
            "active_row_border": "#a2d14988",
        },
        corner_radius=30,
        glass=True,
        layout_style="forest_mist",
    ),
    PlaylistSubTemplate(
        "deep-space",
        "Deep Space",
        _c("#0b1028", "#050814", "#101830aa", "#e0f2fe", "#64748b", "#38bdf8", "#818cf8", "#1e3a5f"),
        corner_radius=14,
    ),
    PlaylistSubTemplate(
        "glass-blur",
        "Glass Blur",
        _c("#2a1838", "#12081c", "#ffffff28", "#f8fafc", "#cbd5e1", "#f0a6ff", "#7c5cff", "#ffffff33"),
        corner_radius=18,
        glass=True,
    ),
    PlaylistSubTemplate(
        "retro-wave",
        "Retro Wave",
        _c("#1a0a2e", "#0f0518", "#2d1b4e88", "#ff71ce", "#c084fc", "#ff71ce", "#01cdfe", "#ff71ce44"),
        corner_radius=8,
        neon_border=True,
    ),
    PlaylistSubTemplate(
        "black-gold",
        "Black & Gold",
        _c("#0a0a0a", "#050505", "#141414", "#fde047", "#a3a3a3", "#eab308", "#fbbf24", "#292524"),
        corner_radius=10,
    ),
    PlaylistSubTemplate(
        "ocean-breeze",
        "Ocean Breeze",
        _c("#e0f7fa", "#b2ebf2", "#ffffffbb", "#0f766e", "#5eead4", "#14b8a6", "#0ea5e9", "#99f6e4"),
        corner_radius=14,
    ),
    PlaylistSubTemplate(
        "deep-forest",
        "Deep Forest",
        _c("#0f1f14", "#081208", "#1a2e1fcc", "#bbf7d0", "#6b7280", "#4ade80", "#22c55e", "#14532d"),
        corner_radius=14,
    ),
    PlaylistSubTemplate(
        "pure-mono",
        "Pure Mono",
        _c("#000000", "#0a0a0a", "#111111", "#ffffff", "#737373", "#ffffff", "#d4d4d4", "#262626"),
        corner_radius=6,
    ),
    PlaylistSubTemplate(
        "cyberpunk",
        "Cyberpunk",
        _c("#0a0014", "#050008", "#1a1030aa", "#00f0ff", "#a78bfa", "#ff3d9a", "#00f0ff", "#ff3d9a33"),
        corner_radius=10,
        neon_border=True,
    ),
)

SUB_TEMPLATES_BY_ID: dict[str, PlaylistSubTemplate] = {t.id: t for t in PLAYLIST_SUB_TEMPLATES}

DEFAULT_SUB_FOR_TEMPLATE: dict[str, str] = {
    "glass-romance": "glass-blur",
    "neon-cyber": "cyberpunk",
    "long-play-green": "forest-mist",
    "golden-hour": "black-gold",
    "vol-collection": "minimal-white",
    "neon-pulse": "retro-wave",
    "midnight-vinyl": "pure-mono",
    "ocean-wave": "ocean-breeze",
    "sakura-dream": "forest-mist",
    "editorial-noir": "pure-mono",
    "aurora-bloom": "deep-space",
    "sunset-drive": "retro-wave",
    "forest-mist": "forest-mist",
    "chrome-reflect": "pure-mono",
    "lavender-haze": "forest-mist",
    "retro-cassette": "retro-wave",
    "ice-crystal": "deep-space",
    "ruby-night": "cyberpunk",
    "mono-classic": "minimal-white",
    "deep-space": "deep-space",
    "candy-pop": "forest-mist",
    "copper-luxe": "black-gold",
    "electric-bars": "glass-blur",
    "pastel-cloud": "forest-mist",
}
