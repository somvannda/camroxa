"""Playlist Stage layout â€” Pulse Railâ€“inspired left hero + right tracklist + bottom bar.

Used when ``titleText.layout == "stage"`` (Purple Neon Glowing Look). All geometry is in
template units against ``renderBaseHeight`` 450 (~800Ã—450 for 16:9).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from features.video.lib.track_display_name import format_title_marker

# ---- canvas (16:9 @ 450) -------------------------------------------------
STAGE_W = 800.0
STAGE_H = 450.0

# Outer stage plate
OUTER = {"x": 36.0, "y": 28.0, "w": 728.0, "h": 394.0, "radius": 22.0}

# Left hero
LEFT_X = 58.0
PILL_Y = 48.0
TITLE_Y = 78.0
ARTIST_Y = 118.0
ART_CX = 168.0
ART_CY = 248.0
ART_R = 78.0
BADGE_X = 268.0
BADGE_Y = 198.0

# Right tracklist card
LIST_X = 420.0
LIST_Y = 72.0
LIST_W = 300.0
LIST_HEADER_H = 22.0

# Bottom bar
BOTTOM_Y = 372.0
BOTTOM_H = 36.0

_DURATION_CACHE: dict[str, float] = {}


def _num(style: dict[str, Any], key: str, default: float) -> float:
    if key not in style or style.get(key) is None:
        return float(default)
    try:
        return float(style.get(key))
    except (TypeError, ValueError):
        return float(default)


def format_track_duration(seconds: float) -> str:
    sec = max(0, int(round(float(seconds or 0.0))))
    return f"{sec // 60}:{sec % 60:02d}"


def probe_track_durations(track_paths: list[str] | None) -> list[float]:
    """Best-effort duration list aligned with track_paths (0.0 when unknown)."""
    from visualizer_video.audio import probe_audio_duration_sec

    out: list[float] = []
    for path in track_paths or []:
        key = str(path or "").strip()
        if not key:
            out.append(0.0)
            continue
        if key in _DURATION_CACHE:
            out.append(_DURATION_CACHE[key])
            continue
        try:
            dur = float(probe_audio_duration_sec(key) or 0.0)
        except Exception:
            dur = 0.0
        _DURATION_CACHE[key] = dur
        out.append(dur)
    return out


def _base_text(
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
    source: str = "titleTextStage",
    box_width: float = 0.0,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "text": text,
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
        "glowBlur": 10.0 if glow > 0.01 else 0.0,
        "letterSpacing": float(letter_spacing),
        "lineSpacing": 1.15,
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


def _pill(
    *,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    border: str,
    source: str,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "overlayKind": "pill",
        "text": text,
        "source": source,
        "anchor": "top-left",
        "x": float(x),
        "y": float(y),
        "panelWidth": float(w),
        "panelHeight": float(h),
        "panelRadius": float(h) * 0.5,
        "panelFrost": 0.2,
        "panelSpecular": 0.55,
        "color": fill,
        "opacity": 0.92,
        "strokeColor": border,
        "strokeWidth": 1.4,
        "sizePx": float(max(7.0, h * 0.42)),
        "fontFamily": "montserrat",
        "bold": True,
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def build_playlist_stage_overlays(
    *,
    title: dict[str, Any],
    titles: list[str],
    active_index: int,
    album_name: str = "",
    logo_path: str = "",
    track_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compose full Purple Neon stage overlays (preview + export)."""
    accent = str(title.get("panelBorderColor") or "#e879f9")
    fill = str(title.get("panelFill") or "#12041c")
    list_color = str(title.get("listColor") or "#f5d0fe")
    active_color = str(title.get("listActiveColor") or "#ffffff")
    show_durations = bool(title.get("showDurations"))
    style = title.get("style") if isinstance(title.get("style"), dict) else {}
    font_size = float(max(9.0, _num(style, "fontSize", 11.5)))
    line_spacing = float(max(1.1, _num(style, "lineSpacing", 1.35)))
    ox = float(_num(style, "x", 0.0))
    oy = float(_num(style, "y", 0.0))
    n = len(titles)
    if n <= 0:
        return []

    idx = int(active_index)
    if idx < 0 or idx >= n:
        idx = 0
    hero_title = str(titles[idx] or "Now Playing").strip() or "Now Playing"
    artist = str(album_name or "").strip() or "LONG PLAY"
    durations = probe_track_durations(track_paths) if show_durations else []

    overlays: list[dict[str, Any]] = []

    def _push(item: dict[str, Any]) -> None:
        item = dict(item)
        if "x" in item:
            item["x"] = float(item.get("x") or 0.0) + ox
        if "y" in item:
            item["y"] = float(item.get("y") or 0.0) + oy
        overlays.append(item)

    # 1) Outer stage glass
    _push(
        _panel(
            x=OUTER["x"],
            y=OUTER["y"],
            w=OUTER["w"],
            h=OUTER["h"],
            fill="#0a0610",
            border=accent,
            opacity=0.55,
            frost=0.45,
            specular=0.7,
            border_w=1.6,
            radius=OUTER["radius"],
            source="titleTextStageOuter",
        )
    )

    # 2) Left: LONG PLAY pill
    _push(
        _pill(
            text="LONG PLAY  â€¢  FULL ALBUM",
            x=LEFT_X,
            y=PILL_Y,
            w=168.0,
            h=16.0,
            fill="#1a0a22",
            border=accent,
            source="titleTextStagePill",
        )
    )

    # 3) Hero title + artist
    _push(
        _base_text(
            text=hero_title,
            x=LEFT_X,
            y=TITLE_Y,
            size=22.0,
            color="#ffffff",
            font="montserrat",
            bold=True,
            glow=0.25,
            glow_color=accent,
            box_width=300.0,
            source="titleTextStageTitle",
        )
    )
    _push(
        _base_text(
            text=artist.upper(),
            x=LEFT_X,
            y=ARTIST_Y,
            size=9.5,
            color=accent,
            font="montserrat",
            bold=True,
            letter_spacing=1.6,
            glow=0.35,
            glow_color=accent,
            source="titleTextStageArtist",
        )
    )

    # 4) Circular art + neon rings (logo if available)
    art_size = ART_R * 2.0
    _push(
        {
            "enabled": True,
            "overlayKind": "stage_art",
            "text": " ",
            "source": "titleTextStageArt",
            "anchor": "top-left",
            "x": ART_CX - ART_R,
            "y": ART_CY - ART_R,
            "panelWidth": art_size,
            "panelHeight": art_size,
            "panelRadius": ART_R,
            "panelFrost": 0.3,
            "panelSpecular": 0.8,
            "color": fill,
            "opacity": 1.0,
            "strokeColor": accent,
            "strokeWidth": 2.0,
            "logoPath": str(logo_path or ""),
            "ringColor": accent,
            "ringCount": 4,
            "animation": "none",
            "startSec": 0.0,
            "durationSec": 1e9,
        }
    )

    # 5) Song-count badge
    _push(
        {
            "enabled": True,
            "overlayKind": "pill",
            "text": f"LONG PLAY\n{n} SONGS",
            "source": "titleTextStageBadge",
            "anchor": "top-left",
            "x": BADGE_X,
            "y": BADGE_Y,
            "panelWidth": 72.0,
            "panelHeight": 72.0,
            "panelRadius": 36.0,
            "panelFrost": 0.25,
            "panelSpecular": 0.6,
            "color": "#140818",
            "opacity": 0.95,
            "strokeColor": accent,
            "strokeWidth": 1.8,
            "sizePx": 8.0,
            "fontFamily": "montserrat",
            "bold": True,
            "animation": "none",
            "startSec": 0.0,
            "durationSec": 1e9,
        }
    )

    # Faint watermark title behind art
    _push(
        _base_text(
            text=hero_title.upper(),
            x=LEFT_X - 10.0,
            y=ART_CY + ART_R + 8.0,
            size=28.0,
            color="#3b0764",
            font="bebasneue",
            bold=False,
            opacity=0.35,
            letter_spacing=1.0,
            box_width=320.0,
            source="titleTextStageWatermark",
        )
    )

    # 6) Right tracklist card
    row_h = float(max(font_size * line_spacing, font_size + 5.0))
    list_pad = 14.0
    list_body_h = row_h * float(n) + 8.0
    list_card_h = LIST_HEADER_H + list_body_h + list_pad * 2.0
    _push(
        _panel(
            x=LIST_X,
            y=LIST_Y,
            w=LIST_W,
            h=list_card_h,
            fill=fill,
            border=accent,
            opacity=float(max(0.45, min(0.85, float(title.get("panelOpacity") or 0.62)))),
            frost=float(max(0.35, float(title.get("panelFrost") or 0.55))),
            specular=float(max(0.5, float(title.get("panelSpecular") or 0.85))),
            border_w=float(max(1.5, float(title.get("panelBorderWidth") or 2.0))),
            radius=14.0,
            source="titleTextPanel",
        )
    )
    _push(
        _base_text(
            text="TRACKLIST",
            x=LIST_X + list_pad,
            y=LIST_Y + list_pad,
            size=8.5,
            color=accent,
            font="montserrat",
            bold=True,
            letter_spacing=2.4,
            glow=0.4,
            glow_color=accent,
            source="titleTextHeader",
        )
    )
    # Header underline
    _push(
        _panel(
            x=LIST_X + list_pad,
            y=LIST_Y + list_pad + 14.0,
            w=LIST_W - list_pad * 2.0,
            h=1.2,
            fill=accent,
            border=accent,
            opacity=0.85,
            frost=0.0,
            specular=0.0,
            border_w=0.0,
            radius=1.0,
            source="titleTextHeaderLine",
        )
    )

    list_style = str(title.get("listStyle") or "plain")
    indent = str(title.get("numberIndent") or "aligned")
    row0_y = LIST_Y + list_pad + LIST_HEADER_H
    for i, name in enumerate(titles):
        y = row0_y + row_h * float(i)
        is_active = i == idx
        if is_active and bool(title.get("activeRowPlate", True)):
           _push(
                _panel(
                    x=LIST_X + 8.0,
                    y=y - 2.0,
                    w=LIST_W - 16.0,
                    h=row_h,
                    fill=accent,
                    border=accent,
                    opacity=0.9,
                    frost=0.2,
                    specular=0.65,
                    border_w=1.0,
                    radius=8.0,
                    source="titleTextActivePlate",
                )
            )
        marker = format_title_marker(i, list_style, total=n, indent=indent)
        label = f"{marker}{name}".strip() if marker else str(name)
        if show_durations and i < len(durations) and durations[i] > 0.05:
            # Duration drawn as separate right-aligned-ish text
           _push(
                _base_text(
                    text=format_track_duration(durations[i]),
                    x=LIST_X + LIST_W - list_pad - 36.0,
                    y=y + 1.0,
                    size=font_size * 0.85,
                    color="#ffffff" if is_active else "#c4b5fd",
                    font="montserrat",
                    bold=False,
                    opacity=0.9 if is_active else 0.7,
                    source="titleText",
                )
            )
        _push(
            _base_text(
                text=label,
                x=LIST_X + list_pad,
                y=y,
                size=font_size,
                color=active_color if is_active else list_color,
                font=str(style.get("fontFamily") or "montserrat"),
                bold=True,
                glow=0.45 if not is_active else 0.15,
                glow_color=accent,
                box_width=LIST_W - list_pad * 2.0 - (40.0 if show_durations else 0.0),
                source="titleText",
            )
        )

    # 7) Bottom transport bar
    _push(
        _panel(
            x=OUTER["x"] + 16.0,
            y=BOTTOM_Y,
            w=OUTER["w"] - 32.0,
            h=BOTTOM_H,
            fill="#100818",
            border=accent,
            opacity=0.7,
            frost=0.3,
            specular=0.4,
            border_w=1.0,
            radius=10.0,
            source="titleTextStageBottom",
        )
    )
    _push(
        _base_text(
            text=f"NOW PLAYING  Â·  {hero_title}",
            x=OUTER["x"] + 28.0,
            y=BOTTOM_Y + 11.0,
            size=8.0,
            color="#f5d0fe",
            font="montserrat",
            bold=True,
            letter_spacing=0.6,
            glow=0.3,
            glow_color=accent,
            source="titleTextStageNowPlaying",
        )
    )
    _push(
        _base_text(
            text="â®   â—€   â–¶   â­",
            x=OUTER["x"] + 280.0,
            y=BOTTOM_Y + 10.0,
            size=10.0,
            color=accent,
            font="montserrat",
            bold=True,
            glow=0.35,
            glow_color=accent,
            source="titleTextStageTransport",
        )
    )
    tag_x = OUTER["x"] + OUTER["w"] - 280.0
    for label, dx in (("RETRO VINYL", 0.0), ("HI-FI", 95.0), ("LONG PLAY", 160.0)):
        _push(
            _pill(
                text=label,
                x=tag_x + dx,
                y=BOTTOM_Y + 9.0,
                w=58.0 if label != "RETRO VINYL" else 86.0,
                h=16.0,
                fill="#14081c",
                border=accent,
                source="titleTextStageTag",
            )
        )

    # Ignore unused Path import warning path check for logo existence is in rasterizer
    _ = Path
    return overlays


def playlist_stage_drag_bounds() -> dict[str, float]:
    """Union frame for CapCut-style drag when stage layout is active."""
    return {
        "x": float(OUTER["x"]),
        "y": float(OUTER["y"]),
        "contentWidth": float(OUTER["w"]),
        "contentHeight": float(OUTER["h"]),
    }

