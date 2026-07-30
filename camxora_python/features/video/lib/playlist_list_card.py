"""Glass Playlist list-card — framed track list only (no full stage).

Matches the boxed playlist reference: header + frosted panel + rows
(number / title / artist / duration) with an outlined active-row frame.
"""

from __future__ import annotations

from typing import Any

from features.video.lib.playlist_stage import format_track_duration, probe_track_durations
from features.video.lib.track_display_name import format_title_marker


def _num(style: dict[str, Any], key: str, default: float) -> float:
    if key not in style or style.get(key) is None:
        return float(default)
    try:
        return float(style.get(key))
    except (TypeError, ValueError):
        return float(default)


def _text(
    *,
    text: str,
    x: float,
    y: float,
    size: float,
    color: str,
    font: str = "montserrat",
    bold: bool = True,
    glow: float = 0.0,
    glow_color: str = "#e879f9",
    letter_spacing: float = 0.0,
    opacity: float = 1.0,
    box_width: float = 0.0,
    source: str = "titleText",
) -> dict[str, Any]:
    return {
        "enabled": True,
        "text": str(text),
        "source": source,
        "anchor": "top-left",
        "x": float(x),
        "y": float(y),
        "sizePx": float(size),
        "fontFamily": font,
        "bold": bool(bold),
        "color": color,
        "strokeWidth": 0.0,
        "shadow": 0.0,
        "glow": float(glow),
        "glowColor": glow_color,
        "glowBlur": 9.0 if glow > 0.01 else 0.0,
        "letterSpacing": float(letter_spacing),
        "lineSpacing": 1.1,
        "boxWidth": float(box_width),
        "align": "left",
        "opacity": float(opacity),
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def _panel(
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    border: str,
    opacity: float,
    frost: float,
    specular: float,
    border_w: float,
    radius: float,
    source: str,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "overlayKind": "panel",
        "text": " ",
        "source": source,
        "anchor": "top-left",
        "x": float(x),
        "y": float(y),
        "panelWidth": float(w),
        "panelHeight": float(h),
        "panelRadius": float(radius),
        "panelFrost": float(frost),
        "panelSpecular": float(specular),
        "color": fill,
        "opacity": float(opacity),
        "strokeColor": border,
        "strokeWidth": float(border_w),
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def build_playlist_list_card_overlays(
    *,
    title: dict[str, Any],
    titles: list[str],
    active_index: int,
    album_name: str = "",
    track_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compose a single glass tracklist card (header + rows)."""
    if not titles:
        return []

    style = title.get("style") if isinstance(title.get("style"), dict) else {}
    base_x = float(_num(style, "x", 390.0))
    base_y = float(_num(style, "y", -20.0))
    card_w = float(max(220.0, _num(style, "boxWidth", 300.0)))
    font_size = float(max(9.0, _num(style, "fontSize", 11.5)))
    accent = str(title.get("panelBorderColor") or title.get("listActiveColor") or "#e879f9")
    fill = str(title.get("panelFill") or "#12041c")
    list_color = str(title.get("listColor") or "#e2e8f0")
    active_color = str(title.get("listActiveColor") or accent)
    muted = "#94a3b8"
    artist = str(album_name or "").strip()
    artist_line = f"v {artist}" if artist and not artist.lower().startswith("v ") else artist
    show_durations = bool(title.get("showDurations", True))
    durations = probe_track_durations(track_paths) if show_durations else []
    list_style = str(title.get("listStyle") or "number_pad")
    indent = str(title.get("numberIndent") or "aligned")
    n = len(titles)
    idx = int(active_index)
    if idx < 0 or idx >= n:
        idx = 0

    # Two-line rows (title + artist) need taller pitch.
    title_h = font_size * 1.15
    artist_h = font_size * 0.85
    row_h = float(title_h + artist_h + 10.0)
    pad = 14.0
    header_h = 22.0
    card_h = pad + header_h + row_h * float(n) + pad

    overlays: list[dict[str, Any]] = []

    # Glass card plate — always draw a visible frame for list_card.
    overlays.append(
        _panel(
            x=base_x,
            y=base_y,
            w=card_w,
            h=card_h,
            fill=fill,
            border=accent,
            opacity=float(max(0.62, min(0.9, float(title.get("panelOpacity") or 0.72)))),
            frost=float(max(0.45, float(title.get("panelFrost") or 0.6))),
            specular=float(max(0.55, float(title.get("panelSpecular") or 0.75))),
            border_w=float(max(2.5, float(title.get("panelBorderWidth") or 2.8))),
            radius=16.0,
            source="titleTextPanel",
        )
    )

    # Header
    header_label = "PLAYLIST"
    if bool(title.get("tracklistHeader", True)):
        overlays.append(
            _text(
                text=header_label,
                x=base_x + pad,
                y=base_y + pad,
                size=8.0,
                color=accent,
                bold=True,
                letter_spacing=2.6,
                glow=0.35,
                glow_color=accent,
                source="titleTextHeader",
            )
        )

    row0 = base_y + pad + header_h
    text_left = base_x + pad + 28.0  # room for index / active icon
    dur_x = base_x + card_w - pad - 42.0
    menu_x = base_x + card_w - pad - 14.0
    title_box = max(80.0, dur_x - text_left - 8.0)

    for i, name in enumerate(titles):
        y = row0 + row_h * float(i)
        is_active = i == idx
        row_color = active_color if is_active else list_color

        if is_active and bool(title.get("activeRowPlate", True)):
            # Outlined glass frame (hollow) around the active row — not a solid bar.
            overlays.append(
                _panel(
                    x=base_x + 8.0,
                    y=y - 3.0,
                    w=card_w - 16.0,
                    h=row_h - 2.0,
                    fill="#0a0a0a",
                    border=accent,
                    opacity=0.35,
                    frost=0.4,
                    specular=0.6,
                    border_w=2.4,
                    radius=10.0,
                    source="titleTextActivePlate",
                )
            )
            # Active icon (waveform / play)
            overlays.append(
                _text(
                    text="♫",
                    x=base_x + pad,
                    y=y + 2.0,
                    size=font_size,
                    color=accent,
                    bold=True,
                    glow=0.45,
                    glow_color=accent,
                    source="titleText",
                )
            )
        else:
            marker = format_title_marker(i, list_style, total=n, indent=indent)
            # Strip trailing punctuation for a clean index column (01 / 02).
            index_text = marker.strip().rstrip(".").rstrip(")")
            if not index_text:
                index_text = f"{i + 1:02d}" if list_style == "number_pad" else str(i + 1)
            overlays.append(
                _text(
                    text=index_text,
                    x=base_x + pad,
                    y=y + 2.0,
                    size=font_size * 0.9,
                    color=muted,
                    bold=False,
                    opacity=0.75,
                    source="titleText",
                )
            )

        overlays.append(
            _text(
                text=str(name),
                x=text_left,
                y=y,
                size=font_size,
                color=row_color,
                bold=True,
                glow=0.4 if is_active else 0.15,
                glow_color=accent,
                box_width=title_box,
                source="titleText",
            )
        )
        if artist_line:
            overlays.append(
                _text(
                    text=artist_line,
                    x=text_left,
                    y=y + title_h + 1.0,
                    size=font_size * 0.72,
                    color=muted if not is_active else "#cbd5e1",
                    bold=False,
                    opacity=0.85,
                    box_width=title_box,
                    source="titleText",
                )
            )

        if show_durations and i < len(durations) and durations[i] > 0.05:
            overlays.append(
                _text(
                    text=format_track_duration(durations[i]),
                    x=dur_x,
                    y=y + 2.0,
                    size=font_size * 0.8,
                    color=row_color if is_active else muted,
                    bold=False,
                    opacity=0.9,
                    source="titleText",
                )
            )
        overlays.append(
            _text(
                text="···",
                x=menu_x,
                y=y + 1.0,
                size=font_size * 0.9,
                color=muted,
                bold=True,
                opacity=0.55,
                source="titleText",
            )
        )

    return overlays


def playlist_list_card_bounds(title: dict[str, Any], titles: list[str]) -> dict[str, float]:
    """Drag-frame size for the glass list card."""
    style = title.get("style") if isinstance(title.get("style"), dict) else {}
    base_x = float(_num(style, "x", 390.0))
    base_y = float(_num(style, "y", -20.0))
    card_w = float(max(220.0, _num(style, "boxWidth", 300.0)))
    font_size = float(max(9.0, _num(style, "fontSize", 11.5)))
    row_h = font_size * 1.15 + font_size * 0.85 + 10.0
    pad = 14.0
    header_h = 22.0
    n = max(1, len(titles))
    card_h = pad + header_h + row_h * float(n) + pad
    return {
        "x": base_x,
        "y": base_y,
        "contentWidth": card_w,
        "contentHeight": card_h,
    }
