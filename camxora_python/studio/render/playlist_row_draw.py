"""Shared PIL drawing for track-row chrome."""

from __future__ import annotations

from studio.core.playlist_row_chrome import PlaylistRowChrome, format_track_number
from studio.core.playlist_row_layout import RowLayoutPlan, compute_row_layout
from PIL import ImageDraw, ImageFont
from studio.ui.icons.lucide_paths import lucide_filled_polygon_points, play_icon_height_for_circle


def parse_hex(hex_color: str) -> tuple[int, int, int, int]:
    raw = (hex_color or "#ffffff").lstrip("#")
    if len(raw) == 8:
        return (
            int(raw[0:2], 16),
            int(raw[2:4], 16),
            int(raw[4:6], 16),
            int(raw[6:8], 16),
        )
    if len(raw) == 6:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 255
    return 255, 255, 255, 255


def fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    trimmed = text
    while trimmed and draw.textlength(trimmed + "…", font=font) > max_w:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed else "…"


def resolve_color(value: str, fallback: str) -> str:
    return value if value else fallback


def draw_equalizer_bars(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    *,
    color,
    heights,
    bar_w: int = 2,
    gap: int = 2,
    total_h: int = 14,
) -> None:
    cx = x
    for ratio in heights:
        bh = max(3, int(total_h * ratio))
        top = y + (total_h - bh) // 2
        draw.rounded_rectangle((cx, top, cx + bar_w, top + bh), radius=1, fill=color)
        cx += bar_w + gap


def draw_play_circle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, bg: str, *, icon: str) -> None:
    r_i = max(1, int(round(r)))
    cx_i, cy_i = int(round(cx)), int(round(cy))
    box = (cx_i - r_i, cy_i - r_i, cx_i + r_i, cy_i + r_i)
    draw.ellipse(box, fill=parse_hex(bg))
    icon_h = play_icon_height_for_circle(r_i)
    tri = lucide_filled_polygon_points("play", float(cx_i), float(cy_i), height_px=icon_h)
    if tri:
        draw.polygon(tri, fill=parse_hex(icon))


def draw_row_chrome(
    draw: ImageDraw.ImageDraw,
    *,
    layout: RowLayoutPlan,
    chrome: PlaylistRowChrome,
    row_index: int,
    playing: bool,
    duration_label: str,
    colors: dict[str, str],
    title: str,
    artist: str | None,
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    num_font: ImageFont.ImageFont,
    bar_heights: tuple[float, ...] | None = None,
    active: bool = False,
) -> None:
    text_color = colors.get("text", "#000000")
    muted = colors.get("muted", "#8e8e93")
    accent = colors.get("accent", text_color)
    button_bg = colors.get("button_inactive", "#ececef")
    play_icon = colors.get("play_icon", accent if active else text_color)
    active_text = colors.get("active_text", accent)

    num_color = resolve_color(
        chrome.numbers.active_color if active else chrome.numbers.color,
        accent if active else muted,
    )
    dur_fill = resolve_color(
        chrome.duration.active_color if active else chrome.duration.color,
        active_text if active else text_color,
    )
    anim_color = resolve_color(
        chrome.animation.active_color if active else chrome.animation.color,
        active_text if active else text_color,
    )
    play_fill = resolve_color(chrome.play.fill_color, button_bg)
    play_icon_color = resolve_color(chrome.play.icon_color, play_icon)
    title_fill = active_text if active else text_color
    meta_fill = active_text if active else muted

    tl = layout.text_layout
    if layout.show_number:
        label = format_track_number(row_index, chrome.numbers.format)
        draw.text((layout.number_x, tl.num_y), label, font=num_font, fill=parse_hex(num_color))

    if layout.show_play:
        draw_play_circle(
            draw,
            layout.play_cx,
            layout.play_cy,
            layout.play_r,
            play_fill,
            icon=play_icon_color,
        )

    draw.text(
        (layout.text_x, tl.title_y),
        fit_text(draw, title, title_font, layout.text_w),
        font=title_font,
        fill=parse_hex(title_fill),
    )
    if artist and tl.artist_y is not None:
        draw.text(
            (layout.text_x, tl.artist_y),
            fit_text(draw, artist.upper(), meta_font, layout.text_w),
            font=meta_font,
            fill=parse_hex(meta_fill),
        )

    if layout.show_duration and duration_label:
        draw.text(
            (layout.duration_x, tl.dur_y),
            duration_label,
            font=meta_font,
            fill=parse_hex(dur_fill),
        )

    if layout.show_animation and bar_heights is not None:
        anim = chrome.animation
        heights = bar_heights[: anim.bar_count]
        draw_equalizer_bars(
            draw,
            layout.animation_x,
            layout.animation_y,
            color=parse_hex(anim_color),
            heights=heights,
            bar_w=anim.bar_width_px,
            gap=anim.bar_gap_px,
            total_h=anim.height_px,
        )


def plan_and_draw_row(
    draw: ImageDraw.ImageDraw,
    *,
    row_x0: int,
    row_x1: int,
    row_y: int,
    row_h: int,
    row_index: int,
    title: str,
    artist: str | None,
    duration_label: str,
    chrome: PlaylistRowChrome,
    colors: dict[str, str],
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    num_font: ImageFont.ImageFont,
    play_r: int,
    playing: bool = False,
    active: bool = False,
    bar_heights: tuple[float, ...] | None = None,
    inset_x: int = 6,
    text_gap: int = 10,
    trailing_gap: int = 8,
) -> None:
    layout = compute_row_layout(
        row_x0=row_x0,
        row_x1=row_x1,
        row_y=row_y,
        row_h=row_h,
        chrome=chrome,
        playing=playing or active,
        duration_label=duration_label,
        draw=draw,
        meta_font=meta_font,
        play_r=play_r,
        title_font=title_font,
        num_font=num_font,
        artist=artist,
        inset_x=inset_x,
        text_gap=text_gap,
        trailing_gap=trailing_gap,
    )
    draw_row_chrome(
        draw,
        layout=layout,
        chrome=chrome,
        row_index=row_index,
        playing=playing or active,
        duration_label=duration_label,
        colors=colors,
        title=title,
        artist=artist,
        title_font=title_font,
        meta_font=meta_font,
        num_font=num_font,
        bar_heights=bar_heights,
        active=active,
    )
