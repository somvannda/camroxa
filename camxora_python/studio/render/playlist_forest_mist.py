"""Forest Mist track list — transparent framed overlay on a forest background."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from studio.core.playlist_settings import PlaylistSettings
from studio.core.project_state import ProjectState
from studio.core.time_utils import fmt_time_ruler
from studio.render.playlist_cache import (
    playlist_media_fingerprint,
    playlist_render_cache,
    playlist_static_card_key,
)
from studio.render.playlist_row_draw import plan_and_draw_row
from studio.ui.icons.lucide_paths import play_circle_radius_for_row

FOREST_MIST_REF_CARD_W = 380
_FOREST_MAX_TRACKS = 10
_FOREST_LAYOUT_TIERS: tuple[int, ...] = (6, 10)
# (row_h, pad_y) — taller rows for title + artist lines; row gap comes from settings.list_row_gap
_FOREST_TIER_PRESETS: dict[int, tuple[int, int]] = {
    6: (56, 32),
    10: (46, 28),
}
_PILL_OUTSET_X = 12
_PILL_OUTSET_Y_MAX = 4
_NUM_COLUMN_W = 30
_ROW_INSET_X = 6


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


def _split_title_artist(media) -> tuple[str, str | None]:
    from studio.render.playlist_minimal_white import _split_title_artist as _split

    return _split(media)


def _bar_heights(*, playback_time: float, band_values, count: int = 4) -> tuple[float, ...]:
    from studio.render.playlist_minimal_white import _bar_heights as _bars

    return _bars(playback_time=playback_time, band_values=band_values, count=count)


def _scaled_font(font_fn, base_px: int, card_w: int) -> ImageFont.ImageFont:
    scale = min(1.0, card_w / FOREST_MIST_REF_CARD_W)
    return font_fn(max(10, int(round(base_px * scale))))


def _text_y_center(font: ImageFont.ImageFont, row_y: int, row_h: int) -> int:
    try:
        ascent, descent = font.getmetrics()
        text_h = ascent + descent
    except Exception:
        text_h = 14
    return row_y + max(0, (row_h - text_h) // 2)


def _text_block_origin(
    row_y: int,
    row_h: int,
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    *,
    line_gap: int = 3,
) -> tuple[int, int]:
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
    if artist:
        title_y, artist_y = _text_block_origin(row_y, row_h, title_font, meta_font)
        num_y = _text_y_center(num_font, row_y, row_h)
        dur_y = _text_y_center(meta_font, row_y, row_h)
        return {"title_y": title_y, "artist_y": artist_y, "num_y": num_y, "dur_y": dur_y}
    line_y = _text_y_center(title_font, row_y, row_h)
    return {
        "title_y": line_y,
        "artist_y": None,
        "num_y": _text_y_center(num_font, row_y, row_h),
        "dur_y": _text_y_center(meta_font, row_y, row_h),
    }


def _layout_tier(song_count: int) -> int:
    if song_count <= 0:
        return 6
    for tier in _FOREST_LAYOUT_TIERS:
        if song_count <= tier:
            return tier
    return _FOREST_LAYOUT_TIERS[-1]


def _plan_forest_layout(w: int, settings: PlaylistSettings, typo) -> dict:
    song_count = len(settings.song_ids)
    row_gap = max(2, int(settings.list_row_gap))
    pad_x = max(24, int(w * 0.075))
    header_gap = max(36, int(typo.song_meta_size * 2.8))

    if song_count == 0:
        # Reserve full card height (like Minimal White's 10-row placeholder) — content stays empty.
        target_rows = _FOREST_LAYOUT_TIERS[-1]
        tier = target_rows
        row_h, pad_y = _FOREST_TIER_PRESETS[tier]
        list_top = pad_y + header_gap
        card_h = list_top + target_rows * row_h + max(0, target_rows - 1) * row_gap + pad_y
        return {
            "pad_x": pad_x,
            "pad_y": pad_y,
            "row_gap": row_gap,
            "row_h": row_h,
            "header_y": pad_y,
            "header_gap": header_gap,
            "list_top": list_top,
            "max_rows": 0,
            "target_rows": target_rows,
            "layout_tier": tier,
            "card_h": int(card_h),
        }

    target_rows = min(max(1, song_count), _FOREST_MAX_TRACKS)
    tier = _layout_tier(song_count)
    row_h, pad_y = _FOREST_TIER_PRESETS[tier]
    list_top = pad_y + header_gap
    card_h = list_top + target_rows * row_h + max(0, target_rows - 1) * row_gap + pad_y
    return {
        "pad_x": pad_x,
        "pad_y": pad_y,
        "row_gap": row_gap,
        "row_h": row_h,
        "header_y": pad_y,
        "header_gap": header_gap,
        "list_top": list_top,
        "max_rows": target_rows,
        "target_rows": target_rows,
        "layout_tier": tier,
        "card_h": int(card_h),
    }


def _layout_metrics(w: int, h: int, settings: PlaylistSettings, typo) -> dict:
    plan = _plan_forest_layout(w, settings, typo)
    if h >= plan["card_h"]:
        return plan
    merged = dict(plan)
    merged["card_h"] = h
    available = max(40, h - plan["list_top"] - plan["pad_y"])
    merged["max_rows"] = min(
        plan["target_rows"],
        max(1, (available + plan["row_gap"]) // max(1, plan["row_h"] + plan["row_gap"])),
    )
    return merged


def forest_mist_card_height(settings: PlaylistSettings, typo, card_w: int = FOREST_MIST_REF_CARD_W) -> int:
    plan = _plan_forest_layout(card_w, settings, typo)
    return max(300, plan["card_h"])


def _draw_rounded_rect(draw, box, fill, radius) -> None:
    draw.rounded_rectangle(box, radius=max(0, radius), fill=fill)


def _draw_equalizer_bars(draw, x, y, *, color, heights, bar_w=2, gap=2, total_h=14) -> None:
    cx = x
    for ratio in heights:
        bh = max(3, int(total_h * ratio))
        top = y + (total_h - bh) // 2
        draw.rounded_rectangle((cx, top, cx + bar_w, top + bh), radius=1, fill=color)
        cx += bar_w + gap


def _draw_play_circle(draw, cx, cy, r, bg, *, icon: str) -> None:
    from studio.render.playlist_minimal_white import _draw_play_circle as _circle

    _circle(draw, cx, cy, r, bg, icon=icon)


def _composite_rgba_patch(dst: np.ndarray, src: np.ndarray, y0: int, x0: int) -> None:
    from studio.render.playlist_minimal_white import _composite_rgba_patch as _patch

    _patch(dst, src, y0, x0)


def _scale_card_rgba(card: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    if card.shape[1] == target_w and card.shape[0] == target_h:
        return card
    scaled = Image.fromarray(card).resize((target_w, target_h), Image.Resampling.LANCZOS)
    return np.ascontiguousarray(np.array(scaled))


def _draw_card_drop_shadow(
    canvas: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    shadow_hex: str,
) -> None:
    from studio.render.playlist_minimal_white import _draw_card_drop_shadow as _shadow

    _shadow(canvas, x, y, w, h, radius, shadow_hex)


def _wipe_row_band(
    card: np.ndarray,
    frame: np.ndarray,
    *,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
) -> None:
    """Clear static text in the active row by restoring the frame layer underneath."""
    y0 = max(0, y0)
    x0 = max(0, x0)
    y1 = min(card.shape[0], y1)
    x1 = min(card.shape[1], x1)
    if y1 <= y0 or x1 <= x0:
        return
    card[y0:y1, x0:x1] = frame[y0:y1, x0:x1]


def _blit_card_to_canvas(canvas: np.ndarray, x: int, y: int, rgba: np.ndarray) -> None:
    from studio.render.playlist_minimal_white import _blit_card_to_canvas as _blit

    _blit(canvas, x, y, rgba)


def _draw_row_divider(
    draw: ImageDraw.ImageDraw,
    row_x0: int,
    row_x1: int,
    div_y: int,
    divider: str,
) -> None:
    draw.line((row_x0 + 8, div_y, row_x1 - 8, div_y), fill=_parse_hex(divider), width=1)


def _draw_three_dots(draw: ImageDraw.ImageDraw, x: int, y: int, *, color: str) -> None:
    fill = _parse_hex(color)
    dot_r, gap = 2, 5
    cy = y + dot_r
    for i in range(3):
        cx = x + i * (dot_r * 2 + gap) + dot_r
        draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=fill)


def _build_transparent_frame_rgba(
    canvas: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    colors: dict[str, str],
) -> np.ndarray:
    """Light frosted veil + rounded border — forest stays visible through the frame."""
    ch, cw = canvas.shape[:2]
    pad = 20
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(cw, x + w + pad)
    y1 = min(ch, y + h + pad)
    patch = canvas[y0:y1, x0:x1]

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    if patch.size == 0:
        return rgba

    blurred = cv2.GaussianBlur(patch, (0, 0), 12)
    off_x, off_y = x - x0, y - y0
    card_rgb = blurred[off_y : off_y + h, off_x : off_x + w].astype(np.float32)

    veil = _parse_hex(colors.get("surface", "#0a120a28"))
    va = veil[3] / 255.0
    veil_rgb = np.array(veil[:3], dtype=np.float32)
    card_rgb = card_rgb * (1.0 - va) + veil_rgb * va

    corner_r = max(4, min(int(radius), w // 2, h // 2))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=corner_r, fill=255)
    mask_arr = np.array(mask, dtype=np.float32) / 255.0

    rgba[..., :3] = np.clip(card_rgb, 0, 255).astype(np.uint8)
    rgba[..., 3] = np.clip(mask_arr * 255, 0, 255).astype(np.uint8)

    border = _parse_hex(colors.get("frame_border", "#a2d14955"))
    if border[3] > 0:
        layer = Image.fromarray(rgba)
        draw = ImageDraw.Draw(layer)
        inset = 1
        border_r = max(3, min(corner_r - 1, (w - 2) // 2, (h - 2) // 2))
        draw.rounded_rectangle(
            (inset, inset, w - 1 - inset, h - 1 - inset),
            radius=border_r,
            outline=(border[0], border[1], border[2], border[3]),
            width=1,
        )
        rgba = np.ascontiguousarray(np.array(layer))

    return rgba


def _row_band(pad_x: int, w: int, row_y: int, row_h: int) -> tuple[int, int, int, int]:
    return pad_x, row_y, w - pad_x, row_y + row_h


def _active_pill_box(pad_x: int, w: int, row_y: int, row_h: int, row_gap: int) -> tuple[int, int, int, int]:
    y_out = min(_PILL_OUTSET_Y_MAX, max(2, row_gap // 2))
    return (
        max(0, pad_x - _PILL_OUTSET_X),
        row_y - y_out,
        min(w, w - pad_x + _PILL_OUTSET_X),
        row_y + row_h + y_out,
    )


def _draw_inactive_row(
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
) -> None:
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
        playing=False,
        active=False,
        inset_x=_ROW_INSET_X,
        text_gap=4,
    )


def _draw_active_row_content(
    draw: ImageDraw.ImageDraw,
    *,
    row_x0: int,
    row_y: int,
    row_x1: int,
    row_h: int,
    title: str,
    artist: str | None,
    duration_label: str,
    settings: PlaylistSettings,
    colors: dict[str, str],
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    bar_heights: tuple[float, ...],
) -> None:
    chrome = settings.row_chrome
    play_r = play_circle_radius_for_row(row_h) * chrome.play.size_scale_pct / 100.0
    plan_and_draw_row(
        draw,
        row_x0=row_x0,
        row_x1=row_x1,
        row_y=row_y,
        row_h=row_h,
        row_index=0,
        title=title,
        artist=artist,
        duration_label=duration_label if chrome.duration.enabled else "",
        chrome=chrome,
        colors=colors,
        title_font=title_font,
        meta_font=meta_font,
        num_font=meta_font,
        play_r=play_r,
        playing=True,
        active=True,
        bar_heights=bar_heights,
        inset_x=_ROW_INSET_X,
        text_gap=4,
        trailing_gap=8,
    )


def _render_static_overlay_rgba(
    w: int,
    h: int,
    *,
    settings: PlaylistSettings,
    project_state: ProjectState,
    colors: dict[str, str],
    font_fn,
    current_index: int = -1,
) -> np.ndarray:
    text_color = colors.get("text", "#ffffff")
    muted = colors.get("muted", "#8a9a8a")
    divider = colors.get("divider", "#ffffff22")
    typo = settings.typography
    metrics = _layout_metrics(w, h, settings, typo)
    from studio.core.playlist_fonts import playlist_row_font_loaders

    header_fn, title_fn, meta_fn = playlist_row_font_loaders(typo)

    rgba = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rgba)

    pad_x = metrics["pad_x"]
    header_y = metrics["header_y"]
    header_font = _scaled_font(header_fn, typo.song_meta_size + 4, w)
    draw.text((pad_x, header_y), "Track List", font=header_font, fill=_parse_hex(text_color))
    _draw_three_dots(draw, w - pad_x - 20, header_y + 2, color=text_color)

    title_font = _scaled_font(title_fn, typo.song_title_size, w)
    meta_font = _scaled_font(meta_fn, typo.song_meta_size, w)
    num_font = _scaled_font(meta_fn, typo.song_meta_size, w)

    row_h = metrics["row_h"]
    row_gap = metrics["row_gap"]
    songs = settings.song_ids[: metrics["max_rows"]]
    if not songs:
        draw.text((pad_x, metrics["list_top"]), "No songs in playlist", font=meta_font, fill=_parse_hex(muted))
    else:
        for index in range(min(len(songs), metrics["max_rows"])):
            if index == current_index:
                continue
            media = project_state.get_media(songs[index])
            if media is None:
                continue
            title, artist = _split_title_artist(media)
            total_dur = float(media.duration or 0)
            duration_label = fmt_time_ruler(total_dur) if settings.row_chrome.duration.enabled and total_dur > 0 else ""
            row_y = metrics["list_top"] + index * (row_h + row_gap)
            row_x0, _, row_x1, _ = _row_band(pad_x, w, row_y, row_h)

            if index > 0 and index != current_index and (index - 1) != current_index:
                div_y = row_y - row_gap // 2
                _draw_row_divider(draw, row_x0, row_x1, div_y, divider)

            _draw_inactive_row(
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
            )

    return np.ascontiguousarray(np.array(rgba))


def _draw_active_row(
    card: np.ndarray,
    frame: np.ndarray,
    *,
    metrics: dict,
    w: int,
    row_index: int,
    media,
    local_time: float,
    bar_heights,
    colors,
    radius,
    font_fn,
    typo,
    settings: PlaylistSettings,
) -> None:
    row_y = metrics["list_top"] + row_index * (metrics["row_h"] + metrics["row_gap"])
    row_h = metrics["row_h"]
    pad_x = metrics["pad_x"]
    row_gap = metrics["row_gap"]

    pill_x0, pill_y0, pill_x1, pill_y1 = _active_pill_box(pad_x, w, row_y, row_h, row_gap)
    _wipe_row_band(card, frame, y0=pill_y0, y1=pill_y1, x0=pill_x0, x1=pill_x1)

    pill_w = pill_x1 - pill_x0
    pill_h = pill_y1 - pill_y0
    if pill_w > 0 and pill_h > 0:
        fill = _parse_hex(colors.get("selected_row", "#1a3d2a66"))
        border = _parse_hex(colors.get("active_row_border", colors.get("accent", "#a2d14988")))
        pill_layer = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
        pill_draw = ImageDraw.Draw(pill_layer)
        pill_radius = max(6, min(pill_h // 2, radius))
        outline = (border[0], border[1], border[2], border[3])
        box = (0, 0, pill_w - 1, pill_h - 1)
        if fill[3] > 0:
            pill_draw.rounded_rectangle(box, radius=pill_radius, fill=fill, outline=outline, width=1)
        else:
            pill_draw.rounded_rectangle(box, radius=pill_radius, outline=outline, width=1)
        _composite_rgba_patch(card, np.array(pill_layer), pill_y0, pill_x0)

    row_x0, _, row_x1, _ = _row_band(pad_x, w, row_y, row_h)
    title, artist = _split_title_artist(media)
    total_dur = float(media.duration or 0)
    duration_label = fmt_time_ruler(total_dur) if total_dur > 0 else fmt_time_ruler(local_time)

    from studio.core.playlist_fonts import playlist_row_font_loaders

    _header_fn, title_fn, meta_fn = playlist_row_font_loaders(typo)
    card_img = Image.fromarray(card)
    draw = ImageDraw.Draw(card_img)
    _draw_active_row_content(
        draw,
        row_x0=row_x0,
        row_y=row_y,
        row_x1=row_x1,
        row_h=row_h,
        title=title,
        artist=artist,
        duration_label=duration_label,
        settings=settings,
        colors=colors,
        title_font=_scaled_font(title_fn, typo.song_title_size + 1, w),
        meta_font=_scaled_font(meta_fn, typo.song_meta_size, w),
        bar_heights=bar_heights,
    )
    card[:] = np.array(card_img)


def draw_forest_mist_track_list(
    canvas: np.ndarray,
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
    ref_w = FOREST_MIST_REF_CARD_W
    ref_h = forest_mist_card_height(settings, typo, ref_w)
    cache = playlist_render_cache()
    media_fp = playlist_media_fingerprint(project_state, settings.song_ids)
    metrics = _layout_metrics(ref_w, ref_h, settings, typo)
    songs = settings.song_ids[: metrics["max_rows"]]
    active_idx = current_index if songs and 0 <= current_index < len(songs) else -1

    static_key = (*playlist_static_card_key(
        settings, ref_w, ref_h, (0, 0, ref_w, ref_h), colors, media_fp,
    ), active_idx)
    static_overlay = cache.get_static_card(
        static_key,
        lambda: _render_static_overlay_rgba(
            ref_w, ref_h,
            settings=settings,
            project_state=project_state,
            colors=colors,
            font_fn=font_fn,
            current_index=active_idx,
        ),
    )

    if w != ref_w or h != ref_h:
        content = _scale_card_rgba(static_overlay, w, h)
    else:
        content = static_overlay

    frame = _build_transparent_frame_rgba(canvas, x, y, w, h, radius, colors)
    card = np.ascontiguousarray(
        np.array(Image.alpha_composite(Image.fromarray(frame), Image.fromarray(content.copy())))
    )

    if active_idx >= 0:
        media = project_state.get_media(songs[active_idx])
        display_metrics = _layout_metrics(w, h, settings, typo)
        if media is not None and active_idx < display_metrics["max_rows"]:
            _draw_active_row(
                card,
                frame,
                metrics=display_metrics,
                w=w,
                row_index=active_idx,
                media=media,
                local_time=local_time,
                bar_heights=_bar_heights(playback_time=playback_time, band_values=band_values),
                colors=colors,
                radius=radius,
                font_fn=font_fn,
                typo=typo,
                settings=settings,
            )

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
