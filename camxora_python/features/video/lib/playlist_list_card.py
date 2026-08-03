"""Glass Playlist list-card — reference Neon Glass Pro reconstruction.

Matches the attached playlist UI spec (no album-art tiles):
glass card, PLAYLIST + N TRACKS header, heart, numbered rows,
title/artist/duration/menu, gradient selected row + equalizer + outer glow.
"""

from __future__ import annotations

from typing import Any

from features.video.lib.playlist_stage import format_track_duration, probe_track_durations
from features.video.lib.track_display_name import format_title_marker

# Spec authored against ~1080p (sf≈2.4 from renderBaseHeight 450).
# Template units ≈ screen_px / 2.4 so 1080p lands near the reference.
_ROW_H = 30.0          # ~72px
_ROW_GAP = 5.0         # ~12px
_PAD = 16.0            # ~38px
_HEADER_H = 44.0       # PLAYLIST + track count
_CARD_RADIUS = 12.5    # ~30px
_ACTIVE_RADIUS = 7.5   # ~18px
_DIVIDER_A = 0.06


def _num(style: dict[str, Any], key: str, default: float) -> float:
    if key not in style or style.get(key) is None:
        return float(default)
    try:
        return float(style.get(key))
    except (TypeError, ValueError):
        return float(default)


def _title_float(title: dict[str, Any], key: str, default: float) -> float:
    if key not in title or title.get(key) is None:
        return float(default)
    try:
        return float(title.get(key))
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
    glow_color: str = "#ffb4da",
    glow_blur: float = 8.0,
    letter_spacing: float = 0.0,
    opacity: float = 1.0,
    box_width: float = 0.0,
    stroke_width: float = 0.0,
    stroke_color: str = "#000000",
    align: str = "left",
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
        "fillMode": "solid",
        "gradientColors": [],
        "strokeWidth": float(max(0.0, stroke_width)),
        "strokeColor": stroke_color,
        "shadow": 0.0,
        "glow": float(glow),
        "glowColor": glow_color,
        "glowBlur": float(glow_blur) if glow > 0.01 else 0.0,
        "letterSpacing": float(letter_spacing),
        "lineSpacing": 1.05,
        "boxWidth": float(box_width),
        "align": align,
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
    fill_mode: str = "solid",
    gradient_colors: list[str] | None = None,
    border_alpha: float = 1.0,
    outer_glow: float = 0.0,
    outer_glow_color: str = "#ffb4da",
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
        "panelFillMode": str(fill_mode or "solid"),
        "panelGradientColors": list(gradient_colors or []),
        "panelBorderAlpha": float(max(0.0, min(1.0, border_alpha))),
        "panelOuterGlow": float(max(0.0, min(1.0, outer_glow))),
        "panelOuterGlowColor": str(outer_glow_color or "#ffb4da"),
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
    """Compose the reference glass tracklist card (no album-art column)."""
    if not titles:
        return []

    style = title.get("style") if isinstance(title.get("style"), dict) else {}
    base_x = float(_num(style, "x", 360.0))
    base_y = float(_num(style, "y", -36.0))
    card_w = float(max(260.0, _num(style, "boxWidth", 340.0)))
    # Spec typography (scaled into template units).
    title_size = float(max(10.0, _num(style, "fontSize", 13.5)))
    artist_size = title_size * 0.75
    number_size = title_size * 0.8
    header_size = title_size * 1.1
    meta_size = title_size * 0.7
    font = str(style.get("fontFamily") or "montserrat")
    text_opacity = float(max(0.15, min(1.0, _num(style, "opacity", 1.0))))

    list_color = str(title.get("listColor") or style.get("color") or "#ffffff")
    active_color = str(title.get("listActiveColor") or list_color or "#ffffff")
    fill = str(title.get("panelFill") or "#6d5b8e")
    border = str(title.get("panelBorderColor") or "#ffffff")
    artist = str(album_name or "").strip()
    # Spec uses plain artist under title (no "v " prefix).
    artist_line = artist
    show_durations = bool(title.get("showDurations", True))
    durations = probe_track_durations(track_paths) if show_durations else []
    list_style = str(title.get("listStyle") or "number_pad")
    indent = str(title.get("numberIndent") or "aligned")
    n = len(titles)
    idx = int(active_index)
    if idx < 0 or idx >= n:
        idx = 0

    panel_opacity = float(max(0.05, min(1.0, _title_float(title, "panelOpacity", 0.8))))
    panel_frost = float(max(0.0, min(1.0, _title_float(title, "panelFrost", 0.7))))
    panel_border = float(max(0.0, min(8.0, _title_float(title, "panelBorderWidth", 0.85))))
    panel_spec = float(max(0.0, min(1.0, _title_float(title, "panelSpecular", 0.45))))

    row_pitch = _ROW_H + _ROW_GAP
    card_h = _PAD + _HEADER_H + row_pitch * float(n) - _ROW_GAP + _PAD

    overlays: list[dict[str, Any]] = []

    # Glass card — white hairline border, lavender frosted plate.
    overlays.append(
        _panel(
            x=base_x,
            y=base_y,
            w=card_w,
            h=card_h,
            fill=fill,
            border=border,
            opacity=panel_opacity,
            frost=panel_frost,
            specular=panel_spec,
            border_w=panel_border,
            radius=_CARD_RADIUS,
            border_alpha=0.25,
            source="titleTextPanel",
        )
    )

    if bool(title.get("tracklistHeader", True)):
        overlays.append(
            _text(
                text="PLAYLIST",
                x=base_x + _PAD,
                y=base_y + _PAD - 2.0,
                size=header_size,
                color="#ffffff",
                font=font,
                bold=True,
                letter_spacing=3.2,
                opacity=text_opacity,
                source="titleTextHeader",
            )
        )
        overlays.append(
            _text(
                text=f"{n} TRACKS",
                x=base_x + _PAD,
                y=base_y + _PAD + header_size * 1.15,
                size=meta_size,
                color="#ffffff",
                font=font,
                bold=False,
                opacity=text_opacity * 0.6,
                source="titleTextHeader",
            )
        )
        # Outline heart (top-right) with soft pink glow.
        overlays.append(
            _text(
                text="♡",
                x=base_x + card_w - _PAD - 16.0,
                y=base_y + _PAD - 2.0,
                size=header_size * 1.15,
                color="#ffffff",
                font=font,
                bold=False,
                glow=0.55,
                glow_color="#ffb4da",
                glow_blur=12.0,
                opacity=text_opacity,
                source="titleTextHeader",
            )
        )

    row0 = base_y + _PAD + _HEADER_H
    num_x = base_x + _PAD
    text_left = base_x + _PAD + 28.0
    dur_x = base_x + card_w - _PAD - 52.0
    menu_x = base_x + card_w - _PAD - 14.0
    title_box = max(70.0, dur_x - text_left - 10.0)

    for i, name in enumerate(titles):
        y = row0 + row_pitch * float(i)
        is_active = i == idx

        # Subtle row dividers (skip above first / under active glow).
        if i > 0 and not is_active and (i - 1) != idx:
            overlays.append(
                _panel(
                    x=base_x + _PAD,
                    y=y - _ROW_GAP * 0.5,
                    w=card_w - _PAD * 2.0,
                    h=0.45,
                    fill="#ffffff",
                    border="#ffffff",
                    opacity=_DIVIDER_A,
                    frost=0.0,
                    specular=0.0,
                    border_w=0.0,
                    radius=0.0,
                    border_alpha=0.0,
                    source="titleTextDivider",
                )
            )

        if is_active and bool(title.get("activeRowPlate", True)):
            # Purple→pink selected pill + outer pink bloom (extends outside row).
            overlays.append(
                _panel(
                    x=base_x + 8.0,
                    y=y - 1.0,
                    w=card_w - 16.0,
                    h=_ROW_H + 2.0,
                    fill="#b76cf6",
                    border="#ffb4da",
                    opacity=0.95,
                    frost=0.15,
                    specular=0.35,
                    border_w=0.0,
                    radius=_ACTIVE_RADIUS,
                    fill_mode="gradient",
                    gradient_colors=["#b76cf6", "#ffb4da"],
                    outer_glow=0.85,
                    outer_glow_color="#ffb4da",
                    source="titleTextActivePlate",
                )
            )
            # Equalizer bars (static glyph stand-in; animation is preview-time later).
            overlays.append(
                _text(
                    text="▍",
                    x=num_x,
                    y=y + (_ROW_H - title_size) * 0.35,
                    size=title_size * 0.95,
                    color="#ffffff",
                    font=font,
                    bold=True,
                    glow=0.25,
                    glow_color="#ffffff",
                    glow_blur=4.0,
                    opacity=1.0,
                    source="titleText",
                )
            )
        else:
            marker = format_title_marker(i, list_style, total=n, indent=indent)
            index_text = marker.strip().rstrip(".").rstrip(")")
            if not index_text:
                index_text = f"{i + 1:02d}" if list_style == "number_pad" else str(i + 1)
            overlays.append(
                _text(
                    text=index_text,
                    x=num_x,
                    y=y + (_ROW_H - number_size) * 0.35,
                    size=number_size,
                    color="#ffffff",
                    font=font,
                    bold=False,
                    opacity=text_opacity * 0.7,
                    source="titleText",
                )
            )

        row_color = active_color if is_active else list_color
        title_y = y + (_ROW_H * 0.18)
        artist_y = title_y + title_size * 1.05
        overlays.append(
            _text(
                text=str(name),
                x=text_left,
                y=title_y,
                size=title_size,
                color=row_color,
                font=font,
                bold=True,
                box_width=title_box,
                opacity=1.0 if is_active else text_opacity,
                source="titleText",
            )
        )
        if artist_line:
            overlays.append(
                _text(
                    text=artist_line,
                    x=text_left,
                    y=artist_y,
                    size=artist_size,
                    color=row_color,
                    font=font,
                    bold=False,
                    box_width=title_box,
                    opacity=1.0 if is_active else text_opacity * 0.6,
                    source="titleText",
                )
            )

        mid_y = y + (_ROW_H - number_size) * 0.35
        if show_durations and i < len(durations) and durations[i] > 0.05:
            overlays.append(
                _text(
                    text=format_track_duration(durations[i]),
                    x=dur_x,
                    y=mid_y,
                    size=number_size,
                    color=row_color,
                    font=font,
                    bold=False,
                    opacity=1.0 if is_active else text_opacity * 0.7,
                    source="titleText",
                )
            )
        overlays.append(
            _text(
                text="⋮",
                x=menu_x,
                y=mid_y - 1.0,
                size=number_size * 1.15,
                color=row_color,
                font=font,
                bold=True,
                opacity=1.0 if is_active else text_opacity * 0.7,
                source="titleText",
            )
        )

    return overlays


def playlist_list_card_bounds(title: dict[str, Any], titles: list[str]) -> dict[str, float]:
    """Drag-frame size for the glass list card."""
    style = title.get("style") if isinstance(title.get("style"), dict) else {}
    base_x = float(_num(style, "x", 360.0))
    base_y = float(_num(style, "y", -36.0))
    card_w = float(max(260.0, _num(style, "boxWidth", 340.0)))
    n = max(1, len(titles))
    row_pitch = _ROW_H + _ROW_GAP
    card_h = _PAD + _HEADER_H + row_pitch * float(n) - _ROW_GAP + _PAD
    return {
        "x": base_x,
        "y": base_y,
        "contentWidth": card_w,
        "contentHeight": card_h,
    }
