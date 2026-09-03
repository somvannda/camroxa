"""Minimal White track-list card — cached static layer + fast dynamic overlay."""

from __future__ import annotations

import math
import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from studio.core.models import MediaAsset
from studio.core.playlist_layout import MINIMAL_WHITE_REF_CARD_H, MINIMAL_WHITE_REF_CARD_W
from studio.core.playlist_settings import PlaylistSettings
from studio.core.project_state import ProjectState
from studio.core.time_utils import fmt_time_ruler
from studio.render.playlist_cache import (
    playlist_card_shadow_key,
    playlist_media_fingerprint,
    playlist_render_cache,
    playlist_static_card_key,
)
from studio.render.playlist_row_draw import plan_and_draw_row
from studio.ui.icons.lucide_paths import (
    lucide_filled_polygon_points,
    play_circle_radius_for_row,
    play_icon_height_for_circle,
)


def _parse_hex(hex_color: str) -> tuple[int, int, int, int]:
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


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    trimmed = text
    while trimmed and draw.textlength(trimmed + "…", font=font) > max_w:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed else "…"


def _clean_track_title(name: str) -> str:
    base = (name or "Untitled").strip()
    stem, ext = os.path.splitext(base)
    if ext.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"):
        base = stem.strip() or base
    # Strip leading track-number prefixes from filenames like "10. Song Name".
    base = re.sub(r"^\d+\s*[.\-_]\s*", "", base).strip()
    return base or "Untitled"


def _split_title_artist(media: MediaAsset) -> tuple[str, str | None]:
    name = _clean_track_title(media.name or "Untitled")
    for sep in (" - ", " – ", " — ", " · "):
        if sep in name:
            left, right = name.split(sep, 1)
            return right.strip() or name, left.strip() or None
    return name, None


def _scaled_font(font_fn, base_px: int, card_w: int, card_h: int | None = None) -> ImageFont.ImageFont:
    """Shrink fonts on small cards only — never upscale beyond configured typography."""
    ref_h = card_h if card_h is not None else MINIMAL_WHITE_REF_CARD_H
    scale = min(1.0, card_w / MINIMAL_WHITE_REF_CARD_W, ref_h / MINIMAL_WHITE_REF_CARD_H)
    return font_fn(max(10, int(round(base_px * scale))))


def _bar_heights(*, playback_time: float, band_values, count: int = 4) -> tuple[float, ...]:
    if band_values is not None and len(band_values) >= count:
        vals = [float(v) for v in band_values[:count]]
        peak = max(vals) if vals else 1.0
        if peak <= 0:
            peak = 1.0
        return tuple(max(0.22, min(1.0, v / peak)) for v in vals)
    t = playback_time
    return tuple(0.28 + 0.62 * abs(math.sin(t * 5.2 + i * 1.45)) for i in range(count))


def _title_font_size(typo) -> int:
    return max(11, typo.song_title_size - 2)


def _meta_font_size(typo) -> int:
    return max(10, typo.song_meta_size - 1)


def _text_y_center(font: ImageFont.ImageFont, row_y: int, row_h: int) -> int:
    try:
        ascent, descent = font.getmetrics()
        text_h = ascent + descent
    except Exception:
        text_h = 14
    return row_y + max(0, (row_h - text_h) // 2)


_MINIMAL_WHITE_MAX_TRACKS = 20
_LAYOUT_TIERS: tuple[int, ...] = (5, 10, 15, 20)
# Pre-calculated (row_h, pad_y) per capacity tier — row gap comes from settings.list_row_gap.
_TIER_PRESETS: dict[int, tuple[int, int]] = {
    5: (60, 31),   # +30% row height, compact chrome
    10: (46, 35),  # reference density
    15: (33, 28),
    20: (26, 24),
}
_FEW_SONGS_MAX_ROWS = 5
_PILL_OUTSET_X = 12  # highlight extends past text band toward card edges
_PILL_OUTSET_Y_MAX = 4
_REF_PAD_Y = 35
_REF_ROW_H = 46
_REF_ROW_GAP = 8
_REF_HEADER_GAP_MULT = 2.5


def _row_content_box(pad_x: int, w: int, row_y: int, row_h: int) -> tuple[int, int, int, int]:
    """Fixed text/icon band — identical for inactive and playing rows."""
    return pad_x, row_y, w - pad_x, row_y + row_h


def _row_pill_box(
    pad_x: int,
    w: int,
    row_y: int,
    row_h: int,
    row_gap: int,
    *,
    target_rows: int = _LAYOUT_TIERS[1],
) -> tuple[int, int, int, int]:
    """Extended highlight pill — wider than the text row; modest vertical bleed."""
    if target_rows <= 5:
        y_out = 0
    else:
        y_out = min(_PILL_OUTSET_Y_MAX, max(2, row_gap // 2))
    return (
        max(0, pad_x - _PILL_OUTSET_X),
        row_y - y_out,
        min(w, w - pad_x + _PILL_OUTSET_X),
        row_y + row_h + y_out,
    )


def _draw_track_row_content(
    draw: ImageDraw.ImageDraw,
    *,
    row_x0: int,
    row_y: int,
    row_x1: int,
    row_h: int,
    row_index: int,
    title: str,
    artist: str | None,
    duration_label: str,
    settings: PlaylistSettings,
    colors: dict[str, str],
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    num_font: ImageFont.ImageFont,
    playing: bool = False,
    bar_heights: tuple[float, ...] | None = None,
) -> None:
    """Draw one track row at fixed content positions (no shift when playing)."""
    chrome = settings.row_chrome
    play_r = play_circle_radius_for_row(row_h) * chrome.play.size_scale_pct / 100.0
    plan_and_draw_row(
        draw,
        row_x0=row_x0,
        row_x1=row_x1,
        row_y=row_y,
        row_h=row_h,
        row_index=row_index,
        title=title,
        artist=artist,
        duration_label=duration_label if chrome.duration.enabled else "",
        chrome=chrome,
        colors=colors,
        title_font=title_font,
        meta_font=meta_font,
        num_font=num_font,
        play_r=play_r,
        playing=playing,
        active=playing,
        bar_heights=bar_heights,
        inset_x=8,
        text_gap=10,
    )


def _text_block_origin(
    row_y: int,
    row_h: int,
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    *,
    line_gap: int = 2,
) -> tuple[int, int]:
    """Vertical center a title + artist block inside a row."""
    try:
        t_ascent, t_descent = title_font.getmetrics()
        m_ascent, m_descent = meta_font.getmetrics()
    except Exception:
        t_ascent, t_descent, m_ascent, m_descent = 12, 3, 9, 2
    block_h = (t_ascent + t_descent) + line_gap + (m_ascent + m_descent)
    top = row_y + max(0, (row_h - block_h) // 2)
    artist_y = top + t_ascent + t_descent + line_gap
    return top, artist_y


def _row_text_layout(
    row_y: int,
    row_h: int,
    *,
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    num_font: ImageFont.ImageFont,
    artist: str | None,
) -> dict[str, int | None]:
    """Vertically center row chrome — number, title, artist, duration."""
    if artist:
        title_y, artist_y = _text_block_origin(row_y, row_h, title_font, meta_font)
        num_y = _text_y_center(num_font, row_y, row_h)
        dur_y = _text_y_center(meta_font, row_y, row_h)
        return {"title_y": title_y, "artist_y": artist_y, "num_y": num_y, "dur_y": dur_y}
    line_y = _text_y_center(title_font, row_y, row_h)
    num_y = _text_y_center(num_font, row_y, row_h)
    dur_y = _text_y_center(meta_font, row_y, row_h)
    return {"title_y": line_y, "artist_y": None, "num_y": num_y, "dur_y": dur_y}


def _layout_capacity_tier(song_count: int) -> int:
    """Map track count to the next layout preset (5 / 10 / 15 / 20)."""
    if song_count <= 0:
        return 10
    for tier in _LAYOUT_TIERS:
        if song_count <= tier:
            return tier
    return _LAYOUT_TIERS[-1]


def _plan_track_list_layout(w: int, settings: PlaylistSettings, typo) -> dict:
    """Pre-calculate row spacing and card height for the current track count."""
    song_count = len(settings.song_ids)
    target_rows = min(max(1, song_count), _MINIMAL_WHITE_MAX_TRACKS) if song_count else 10
    tier = _layout_capacity_tier(song_count or 10)
    row_h, pad_y = _TIER_PRESETS[tier]
    row_gap = max(2, int(settings.list_row_gap))

    pad_x = max(22, int(w * 0.075))
    title_px = _title_font_size(typo)
    min_row_h = max(22, int(title_px * 1.35))
    min_row_gap = 2
    min_pad_y = 12
    min_header_gap = max(16, int(typo.song_meta_size * 1.35))
    row_h = max(min_row_h, row_h)
    header_gap = int(round(typo.song_meta_size * _REF_HEADER_GAP_MULT))

    card_h = pad_y + header_gap + target_rows * row_h + max(0, target_rows - 1) * row_gap + pad_y
    list_top = pad_y + header_gap

    return {
        "pad_x": pad_x,
        "pad_y": pad_y,
        "row_gap": row_gap,
        "row_h": row_h,
        "header_y": pad_y,
        "header_gap": header_gap,
        "list_top": list_top,
        "footer_h": 0,
        "max_rows": target_rows,
        "target_rows": target_rows,
        "layout_tier": tier,
        "card_h": int(card_h),
    }


def _layout_metrics(w: int, h: int, settings: PlaylistSettings, typo) -> dict:
    plan = _plan_track_list_layout(w, settings, typo)
    if h >= plan["card_h"]:
        return plan

    # Rare fallback: compress into a shorter render target if needed.
    pad_y = plan["pad_y"]
    header_gap = plan["header_gap"]
    row_gap = plan["row_gap"]
    row_h = plan["row_h"]
    target_rows = plan["target_rows"]
    title_px = _title_font_size(typo)
    min_row_h = max(22, int(title_px * 1.35))
    min_row_gap = 2
    min_pad_y = max(12, int(h * 0.022))
    min_header_gap = max(16, int(typo.song_meta_size * 1.35))

    def _list_fits(*, pad_y_v: int, header_gap_v: int, row_gap_v: int, row_h_v: int, rows: int) -> bool:
        list_top_v = pad_y_v + header_gap_v
        available = h - list_top_v - pad_y_v
        needed = rows * row_h_v + max(0, rows - 1) * row_gap_v
        return needed <= available

    if not _list_fits(
        pad_y_v=pad_y,
        header_gap_v=header_gap,
        row_gap_v=row_gap,
        row_h_v=row_h,
        rows=target_rows,
    ):
        guard = 0
        while not _list_fits(
            pad_y_v=pad_y,
            header_gap_v=header_gap,
            row_gap_v=row_gap,
            row_h_v=row_h,
            rows=target_rows,
        ):
            guard += 1
            if guard > 200:
                break
            if row_gap > min_row_gap:
                row_gap -= 1
            elif pad_y > min_pad_y:
                pad_y = max(min_pad_y, pad_y - 2)
            elif header_gap > min_header_gap:
                header_gap = max(min_header_gap, header_gap - 1)
            elif row_h > min_row_h:
                row_h = max(min_row_h, row_h - 1)
            else:
                break

    list_top = pad_y + header_gap
    available = max(40, h - list_top - pad_y)
    max_rows = min(target_rows, max(1, (available + row_gap) // max(1, row_h + row_gap)))

    merged = dict(plan)
    merged.update(
        {
            "pad_y": pad_y,
            "row_gap": row_gap,
            "row_h": row_h,
            "header_y": pad_y,
            "header_gap": header_gap,
            "list_top": list_top,
            "max_rows": max_rows,
            "card_h": h,
        }
    )
    return merged


def minimal_white_card_height(
    settings: PlaylistSettings,
    typo,
    card_w: int = MINIMAL_WHITE_REF_CARD_W,
) -> int:
    """Card height sized to fit every track — width stays at ref card width."""
    plan = _plan_track_list_layout(card_w, settings, typo)
    return max(280, plan["card_h"])


def _draw_rounded_rect(draw, box, fill, radius) -> None:
    draw.rounded_rectangle(box, radius=max(0, radius), fill=fill)


def _draw_equalizer_bars(draw, x, y, *, color, heights, bar_w=3, gap=3, total_h=16) -> None:
    cx = x
    for ratio in heights:
        bh = max(3, int(total_h * ratio))
        top = y + (total_h - bh) // 2
        draw.rounded_rectangle((cx, top, cx + bar_w, top + bh), radius=1, fill=color)
        cx += bar_w + gap


def _draw_play_circle(draw, cx, cy, r, bg, *, icon: str = "#000000") -> None:
    r = max(1, int(round(r)))
    cx_i, cy_i = int(round(cx)), int(round(cy))
    box = (cx_i - r, cy_i - r, cx_i + r, cy_i + r)
    draw.ellipse(box, fill=_parse_hex(bg))
    icon_h = play_icon_height_for_circle(r)
    tri = lucide_filled_polygon_points("play", float(cx_i), float(cy_i), height_px=icon_h)
    if tri:
        draw.polygon(tri, fill=_parse_hex(icon))


def _render_static_card_rgba(
    w: int,
    h: int,
    *,
    settings: PlaylistSettings,
    project_state: ProjectState,
    colors: dict[str, str],
    radius: int,
    font_fn,
) -> np.ndarray:
    """Build the card layer once (shadow, chrome, inactive rows) with alpha."""
    text_color = colors.get("text", "#000000")
    muted = colors.get("muted", "#8e8e93")
    surface = colors.get("surface", "#ffffff")
    button_inactive = colors.get("button_inactive", "#ececef")
    divider = colors.get("divider", "#e5e5ea")
    typo = settings.typography
    metrics = _layout_metrics(w, h, settings, typo)
    from core.playlist_fonts import playlist_row_font_loaders

    header_fn, title_fn, meta_fn = playlist_row_font_loaders(typo)

    rgba = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rgba)
    _draw_rounded_rect(draw, (0, 0, w, h), _parse_hex(surface), radius)

    pad_x = metrics["pad_x"]
    header_y = metrics["header_y"]
    header_font = _scaled_font(header_fn, typo.song_meta_size + 1, w)
    draw.text((pad_x, header_y), "TRACK LIST", font=header_font, fill=_parse_hex(text_color))
    title_w = draw.textlength("TRACK LIST", font=header_font)
    _draw_equalizer_bars(
        draw,
        int(pad_x + title_w + 10),
        header_y + 1,
        color=_parse_hex(text_color),
        heights=(0.5, 0.9, 0.6, 0.95),
        total_h=12,
        bar_w=2,
        gap=2,
    )

    title_font = _scaled_font(title_fn, _title_font_size(typo), w)
    meta_font = _scaled_font(meta_fn, _meta_font_size(typo), w)
    num_font = _scaled_font(meta_fn, _meta_font_size(typo), w)

    row_h = metrics["row_h"]
    row_gap = metrics["row_gap"]
    list_top = metrics["list_top"]
    songs = settings.song_ids[: metrics["max_rows"]]

    if not songs:
        draw.text((pad_x, list_top), "No songs in playlist", font=meta_font, fill=_parse_hex(muted))
    else:
        for index in range(min(len(songs), metrics["max_rows"])):
            media = project_state.get_media(songs[index])
            if media is None:
                continue
            title, artist = _split_title_artist(media)
            total_dur = float(media.duration or 0)
            duration_label = fmt_time_ruler(total_dur) if settings.row_chrome.duration.enabled and total_dur > 0 else ""

            row_y = list_top + index * (row_h + row_gap)
            row_x0, _, row_x1, row_y2 = _row_content_box(pad_x, w, row_y, row_h)
            row_box = (row_x0, row_y, row_x1, row_y2)

            if index > 0:
                div_y = row_y - row_gap // 2
                draw.line((row_box[0] + 8, div_y, row_box[2] - 8, div_y), fill=_parse_hex(divider), width=1)

            _draw_track_row_content(
                draw,
                row_x0=row_x0,
                row_y=row_y,
                row_x1=row_x1,
                row_h=row_h,
                row_index=index,
                title=title,
                artist=artist,
                duration_label=duration_label,
                settings=settings,
                colors=colors,
                title_font=title_font,
                meta_font=meta_font,
                num_font=num_font,
                playing=False,
            )

    return np.ascontiguousarray(np.array(rgba))


def _composite_rgba_patch(dst: np.ndarray, src: np.ndarray, y0: int, x0: int) -> None:
    """Alpha-composite ``src`` RGBA patch onto ``dst`` RGBA at offset."""
    sh, sw = src.shape[:2]
    region = dst[y0 : y0 + sh, x0 : x0 + sw].astype(np.float32)
    s_rgb = src[..., :3].astype(np.float32)
    s_a = src[..., 3:4].astype(np.float32) / 255.0
    d_a = region[..., 3:4] / 255.0
    out_a = np.maximum(s_a + d_a * (1.0 - s_a), 1e-6)
    out_rgb = (s_rgb * s_a + region[..., :3] * d_a * (1.0 - s_a)) / out_a
    dst[y0 : y0 + sh, x0 : x0 + sw, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    dst[y0 : y0 + sh, x0 : x0 + sw, 3] = np.clip(out_a[..., 0] * 255.0, 0, 255).astype(np.uint8)


def _build_card_shadow_rgba(w: int, h: int, radius: int, shadow_hex: str) -> np.ndarray:
    pad = 28
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    ox, oy = pad, pad + 4
    draw.rounded_rectangle((ox, oy, ox + w, oy + h), radius=radius, fill=_parse_hex(shadow_hex))
    return np.array(layer.filter(ImageFilter.GaussianBlur(radius=18)))


def _draw_card_drop_shadow(
    canvas: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    shadow_hex: str,
) -> None:
    """Soft drop shadow behind the card — cached, not recomputed every frame."""
    pad = 28
    shadow = playlist_render_cache().get_card_shadow(
        playlist_card_shadow_key(w, h, radius, shadow_hex),
        lambda: _build_card_shadow_rgba(w, h, radius, shadow_hex),
    )
    _blit_rgba_to_rgb(canvas, x - pad, y - pad + 2, shadow)


def _blit_card_to_canvas(canvas: np.ndarray, x: int, y: int, rgba: np.ndarray) -> None:
    """Place the card without a gray anti-aliased border fringe."""
    ch, cw = rgba.shape[:2]
    canvas_h, canvas_w = canvas.shape[:2]
    src_x0 = max(0, -x)
    src_y0 = max(0, -y)
    dst_x0 = max(0, x)
    dst_y0 = max(0, y)
    copy_w = min(cw - src_x0, canvas_w - dst_x0)
    copy_h = min(ch - src_y0, canvas_h - dst_y0)
    if copy_w <= 0 or copy_h <= 0:
        return
    src = rgba[src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w]
    dest = canvas[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w]
    alpha = src[..., 3]
    rgb = src[..., :3]
    solid = alpha >= 200
    dest[solid] = rgb[solid]
    fringe = (alpha > 0) & (~solid)
    if np.any(fringe):
        a = alpha[fringe].astype(np.float32) / 255.0
        base = dest[fringe].astype(np.float32)
        dest[fringe] = np.clip(base * (1.0 - a[:, None]) + rgb[fringe].astype(np.float32) * a[:, None], 0, 255).astype(
            np.uint8
        )


def _blit_rgba_to_rgb(canvas: np.ndarray, x: int, y: int, rgba: np.ndarray) -> None:
    """Composite RGBA onto RGB canvas, clipping at canvas bounds."""
    ch, cw = rgba.shape[:2]
    canvas_h, canvas_w = canvas.shape[:2]
    src_x0 = max(0, -x)
    src_y0 = max(0, -y)
    dst_x0 = max(0, x)
    dst_y0 = max(0, y)
    copy_w = min(cw - src_x0, canvas_w - dst_x0)
    copy_h = min(ch - src_y0, canvas_h - dst_y0)
    if copy_w <= 0 or copy_h <= 0:
        return
    src = rgba[src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w]
    dest = canvas[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w].astype(np.float32)
    rgb = src[..., :3].astype(np.float32)
    a = src[..., 3:4].astype(np.float32) / 255.0
    canvas[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w] = np.clip(
        dest * (1.0 - a) + rgb * a, 0, 255
    ).astype(np.uint8)


def _draw_active_row_cv2(
    card: np.ndarray,
    *,
    row_y: int,
    row_h: int,
    row_gap: int,
    pad_x: int,
    w: int,
    settings: PlaylistSettings,
    media: MediaAsset,
    row_index: int,
    local_time: float,
    bar_heights: tuple[float, ...],
    colors: dict[str, str],
    radius: int,
    font_fn,
    typo,
    has_row_below: bool = False,
    target_rows: int = _LAYOUT_TIERS[1],
) -> None:
    """Replace the active row — extended pill behind fixed content positions."""
    surface = _parse_hex(colors.get("surface", "#ffffff"))
    selected = _parse_hex(colors.get("selected_row", "#f2f2f7"))

    row_x0, _, row_x1, row_y2 = _row_content_box(pad_x, w, row_y, row_h)
    pill_x0, pill_y0, pill_x1, pill_y1 = _row_pill_box(
        pad_x, w, row_y, row_h, row_gap, target_rows=target_rows
    )
    pill_w = pill_x1 - pill_x0
    pill_h = pill_y1 - pill_y0
    if row_h <= 0 or pill_w <= 0 or pill_h <= 0:
        return

    if row_index > 0:
        div_y = row_y - row_gap // 2
        card[div_y : div_y + 1, row_x0 + 8 : row_x1 - 8, :3] = surface[:3]
        card[div_y : div_y + 1, row_x0 + 8 : row_x1 - 8, 3] = 255

    if has_row_below:
        div_below = row_y2 + row_gap // 2
        if div_below < card.shape[0]:
            card[div_below : div_below + 1, row_x0 + 8 : row_x1 - 8, :3] = surface[:3]
            card[div_below : div_below + 1, row_x0 + 8 : row_x1 - 8, 3] = 255

    card[row_y:row_y2, row_x0:row_x1, :3] = surface[:3]
    card[row_y:row_y2, row_x0:row_x1, 3] = 255

    pill_layer = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill_layer)
    _draw_rounded_rect(
        pill_draw,
        (0, 0, pill_w - 1, pill_h - 1),
        selected,
        max(6, min(pill_h // 2, radius)),
    )
    _composite_rgba_patch(card, np.array(pill_layer), pill_y0, pill_x0)

    from core.playlist_fonts import playlist_row_font_loaders

    _header_fn, title_fn, meta_fn = playlist_row_font_loaders(typo)
    title_font = _scaled_font(title_fn, _title_font_size(typo), w)
    meta_font = _scaled_font(meta_fn, _meta_font_size(typo), w)
    num_font = _scaled_font(meta_fn, _meta_font_size(typo), w)

    title, artist = _split_title_artist(media)
    duration_label = fmt_time_ruler(local_time)

    card_img = Image.fromarray(card)
    draw = ImageDraw.Draw(card_img)
    _draw_track_row_content(
        draw,
        row_x0=row_x0,
        row_y=row_y,
        row_x1=row_x1,
        row_h=row_h,
        row_index=row_index,
        title=title,
        artist=artist,
        duration_label=duration_label,
        settings=settings,
        colors=colors,
        title_font=title_font,
        meta_font=meta_font,
        num_font=num_font,
        playing=True,
        bar_heights=bar_heights,
    )
    card[:] = np.array(card_img)


def _scale_card_rgba(card: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    if card.shape[1] == target_w and card.shape[0] == target_h:
        return card
    scaled = Image.fromarray(card).resize((target_w, target_h), Image.Resampling.LANCZOS)
    return np.ascontiguousarray(np.array(scaled))


def draw_minimal_white_track_list(
    canvas,
    rect: tuple[int, int, int, int],
    *,
    settings: PlaylistSettings,
    project_state: ProjectState,
    current_index: int,
    local_time: float,
    playback_time: float,
    band_values,
    colors: dict[str, str],
    radius: int,
    font_fn,
    canvas_w: int,
    canvas_h: int,
) -> None:
    x, y, w, h = rect
    if w <= 8 or h <= 8:
        return

    typo = settings.typography
    ref_w = MINIMAL_WHITE_REF_CARD_W
    ref_h = minimal_white_card_height(settings, typo, ref_w)
    cache = playlist_render_cache()
    media_fp = playlist_media_fingerprint(project_state, settings.song_ids)
    static_key = playlist_static_card_key(
        settings,
        ref_w,
        ref_h,
        (0, 0, ref_w, ref_h),
        colors,
        media_fp,
    )
    static_card = cache.get_static_card(
        static_key,
        lambda: _render_static_card_rgba(
            ref_w,
            ref_h,
            settings=settings,
            project_state=project_state,
            colors=colors,
            radius=radius,
            font_fn=font_fn,
        ),
    )

    card = static_card.copy()
    metrics = _layout_metrics(ref_w, ref_h, settings, typo)
    songs = settings.song_ids[: metrics["max_rows"]]

    if songs and 0 <= current_index < len(songs):
        media = project_state.get_media(songs[current_index])
        if media is not None and current_index < metrics["max_rows"]:
            row_y = metrics["list_top"] + current_index * (metrics["row_h"] + metrics["row_gap"])
            heights = _bar_heights(playback_time=playback_time, band_values=band_values)
            _draw_active_row_cv2(
                card,
                row_y=row_y,
                row_h=metrics["row_h"],
                row_gap=metrics["row_gap"],
                pad_x=metrics["pad_x"],
                w=ref_w,
                settings=settings,
                media=media,
                row_index=current_index,
                local_time=local_time,
                bar_heights=heights,
                colors=colors,
                radius=radius,
                font_fn=font_fn,
                typo=typo,
                has_row_below=current_index < len(songs) - 1,
                target_rows=metrics["target_rows"],
            )

    if w != ref_w or h != ref_h:
        card = _scale_card_rgba(card, w, h)

    _draw_card_drop_shadow(
        canvas,
        x,
        y,
        w,
        h,
        radius,
        colors.get("card_shadow", "#00000045"),
    )
    _blit_card_to_canvas(canvas, x, y, card)
