"""Five-slot color palettes for Minimal White track-list cards.

Visible roles on the card:
  1. background  — page gradient behind the card
  2. surface     — card fill
  3. text        — titles, numbers, durations, icons (true black on light themes)
  4. muted       — artist subtitles, dividers, inactive button fills
  5. selected    — currently playing row highlight
"""

from __future__ import annotations

PALETTE_SLOT_COUNT = 5
Palette5 = tuple[str, str, str, str, str]

# Keys edited in the Settings panel (one per palette slot for Minimal White).
PALETTE_SLOT_KEYS: tuple[str, ...] = ("bg_from", "surface", "text", "muted", "selected_row")
# Standalone track-list templates — scene background uses bundled PNG; hide bg_from in the UI.
STANDALONE_CUSTOM_COLOR_KEYS: tuple[str, ...] = ("surface", "text", "active_text", "muted", "selected_row")
# Keys that map to the five preset palette chips (active_text is a separate override).
STANDALONE_PALETTE_SLOT_KEYS: tuple[str, ...] = ("surface", "text", "muted", "selected_row")
PALETTE_SLOT_LABELS: dict[str, str] = {
    "bg_from": "Background",
    "surface": "Card",
    "text": "Text",
    "active_text": "Active text",
    "muted": "Muted",
    "selected_row": "Active row fill",
}

# Glass / full-scene templates — accent-driven palette.
GLASS_COLOR_KEYS: tuple[tuple[str, str], ...] = (
    ("accent", "Accent"),
    ("accent2", "Accent 2"),
    ("text", "Text"),
    ("muted", "Muted"),
)


def _channel(value: int) -> int:
    return max(0, min(255, value))


def _parse_rgb(hex_color: str) -> tuple[int, int, int]:
    raw = hex_color.lstrip("#")
    if len(raw) == 8:
        raw = raw[:6]
    if len(raw) != 6:
        return 128, 128, 128
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _to_hex(r: int, g: int, b: int) -> str:
    return f"#{_channel(r):02x}{_channel(g):02x}{_channel(b):02x}"


def _lighten(hex_color: str, amount: float) -> str:
    r, g, b = _parse_rgb(hex_color)
    return _to_hex(
        int(r + (255 - r) * amount),
        int(g + (255 - g) * amount),
        int(b + (255 - b) * amount),
    )


def _blend(a: str, b: str, t: float) -> str:
    ar, ag, ab = _parse_rgb(a)
    br, bg, bb = _parse_rgb(b)
    u = max(0.0, min(1.0, t))
    return _to_hex(
        int(ar + (br - ar) * u),
        int(ag + (bg - ag) * u),
        int(ab + (bb - ab) * u),
    )


def _resolve_active_row_fill(selected: str, background: str) -> str:
    """Use explicit RGBA from the picker; preset chips without alpha keep Forest Mist defaults."""
    raw = selected.lstrip("#")
    if len(raw) == 8:
        return f"#{raw.lower()}"
    if len(raw) == 6:
        return _blend(background, "#1a3d2a", 0.65) + "66"
    return "#1a3d2a66"


def hex_to_qcolor(hex_color: str) -> "QColor":
    from PySide6.QtGui import QColor

    raw = (hex_color or "#ffffff").lstrip("#")
    if len(raw) == 8:
        return QColor(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), int(raw[6:8], 16))
    if len(raw) == 6:
        return QColor(f"#{raw}")
    return QColor("#ffffff")


def qcolor_to_hex(color: "QColor", *, with_alpha: bool = False) -> str:
    if with_alpha or color.alpha() < 255:
        return f"#{color.red():02x}{color.green():02x}{color.blue():02x}{color.alpha():02x}"
    return color.name()


def swatch_stylesheet(hex_color: str) -> str:
    color = hex_to_qcolor(hex_color)
    return (
        f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha() / 255.0});"
        " border: 1px solid #3a4466; border-radius: 6px;"
    )


def hex_with_alpha_percent(rgb_hex: str, alpha_pct: int) -> str:
    raw = (rgb_hex or "#ffffff").lstrip("#")[:6]
    alpha = max(0, min(255, int(round(alpha_pct / 100.0 * 255))))
    return f"#{raw}{alpha:02x}"


def rgba_alpha_percent(hex_color: str) -> int:
    raw = (hex_color or "").lstrip("#")
    if len(raw) == 8:
        return int(round(int(raw[6:8], 16) / 255.0 * 100))
    return 100


def rgb_hex_from_color(hex_color: str) -> str:
    raw = (hex_color or "#ffffff").lstrip("#")
    if len(raw) >= 6:
        return f"#{raw[0:6]}"
    return "#ffffff"


def pick_color_hex(
    parent,
    *,
    title: str,
    current: str,
    with_alpha: bool = False,
) -> str | None:
    """Open a color dialog. Prefer the panel opacity slider for active-row alpha on Windows."""
    from PySide6.QtWidgets import QColorDialog

    seed = rgb_hex_from_color(current) if not with_alpha else current
    dialog = QColorDialog(hex_to_qcolor(seed), parent)
    dialog.setWindowTitle(title)
    dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
    if with_alpha:
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
    if dialog.exec() != QColorDialog.DialogCode.Accepted:
        return None
    picked = dialog.selectedColor()
    if not picked.isValid():
        return None
    if with_alpha:
        return qcolor_to_hex(picked, with_alpha=True)
    return picked.name()


def palette_from_colors(colors: dict[str, str]) -> Palette5:
    """Read the five Minimal White slots from a resolved color dict."""
    return (
        colors.get("bg_from", "#e8eaee"),
        colors.get("surface", "#ffffff"),
        colors.get("text", "#000000"),
        colors.get("muted", "#8e8e93"),
        colors.get("selected_row", "#f2f2f7"),
    )


def apply_palette_slot(colors: dict[str, str], slot_key: str, hex_color: str) -> dict[str, str]:
    """Update one palette slot and re-expand derived Minimal White colors."""
    return apply_palette_slot_for_layout(colors, slot_key, hex_color, layout_style="minimal_white")


def apply_palette_slot_for_layout(
    colors: dict[str, str],
    slot_key: str,
    hex_color: str,
    *,
    layout_style: str,
) -> dict[str, str]:
    """Update one palette slot and re-expand track-list colors for the layout."""
    if slot_key not in PALETTE_SLOT_KEYS:
        return dict(colors)
    palette = list(palette_from_colors(colors))
    palette[PALETTE_SLOT_KEYS.index(slot_key)] = hex_color
    if layout_style == "forest_mist":
        return expand_forest_mist_palette(*palette)
    return expand_palette(*palette)


def expand_palette(background: str, surface: str, text: str, muted: str, selected: str) -> dict[str, str]:
    """Expand 5 palette slots into the full Minimal White color dict."""
    accent = text
    return {
        "bg_from": background,
        "bg_to": _lighten(background, 0.055),
        "surface": surface,
        "text": text,
        "muted": muted,
        "active_text": accent,
        "play_icon": text,
        "icon": text,
        "divider": _blend(surface, muted, 0.42),
        "button_inactive": _blend(surface, muted, 0.22),
        "button_active": surface,
        "selected_row": selected if len(selected.lstrip("#")) in (6, 8) else "#f2f2f7",
        "accent": accent,
        "accent2": muted,
        "active_glow": f"{text}40" if len(text) == 7 else text,
        "card_shadow": "#00000045",
    }


def expand_forest_mist_palette(background: str, surface: str, text: str, muted: str, selected: str) -> dict[str, str]:
    """Expand 5 palette slots into Forest Mist transparent-frame colors."""
    surface_hex = surface[:7] if len(surface) >= 7 else surface
    frame_veil = surface_hex + "28" if len(surface_hex) == 7 else surface
    accent = _blend(selected, "#a2d149", 0.55)
    if len(accent) == 7 and accent.lower().startswith("#a2"):
        accent = "#a2d149"
    pill_fill = _resolve_active_row_fill(selected, background)
    border = accent + "88" if len(accent) == 7 else accent
    return {
        "bg_from": background,
        "bg_to": _blend(background, "#000000", 0.35),
        "surface": frame_veil,
        "frame_border": _blend(muted, text, 0.45) + "66" if len(_blend(muted, text, 0.45)) == 7 else _blend(muted, text, 0.45),
        "text": text,
        "muted": muted,
        "active_text": accent,
        "selected_row": pill_fill,
        "accent": accent,
        "accent2": _lighten(accent, 0.12),
        "play_icon": accent,
        "button_inactive": _blend(background, "#0f2218", 0.7),
        "button_active": surface_hex,
        "divider": "#ffffff22",
        "card_shadow": "#00000045",
        "active_row_border": border,
        "active_glow": f"{accent}30" if len(accent) == 7 else accent,
    }


def palette_chip_stylesheet(palette: Palette5, *, selected: bool = False) -> str:
    """Five solid stripes — one per palette slot (no blended gradients)."""
    border = "2px solid #7466F1" if selected else "1px solid #444"
    stops: list[str] = []
    for index, color in enumerate(palette):
        start = index / PALETTE_SLOT_COUNT
        end = (index + 1) / PALETTE_SLOT_COUNT - 0.001
        stops.append(f"stop:{start:.3f} {color}, stop:{end:.3f} {color}")
    stop_css = ", ".join(stops)
    return (
        "QPushButton {"
        f" border: {border}; border-radius: 6px;"
        f" background: qlineargradient(x1:0,y1:0,x2:1,y2:0, {stop_css});"
        " }"
    )
