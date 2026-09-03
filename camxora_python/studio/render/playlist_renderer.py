"""Draw playlist template onto the compositor canvas."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from studio.render.playlist_cache import (
    background_mtime_ns,
    cached_background_cover,
    playlist_background_key,
    playlist_render_cache,
)
from studio.core.playlist_assets import resolve_playlist_background
from studio.core.playlist_fonts import playlist_font, playlist_font_fn
from studio.core.playlist_layout import is_standalone_track_list_layout, rect_to_pixels, resolve_component_layout
from studio.core.playlist_settings import PLAYLIST_COMPONENTS, PlaylistSettings
from studio.core.playlist_style import resolve_playlist_colors
from studio.core.playlist_sub_templates import SUB_TEMPLATES_BY_ID
from studio.core.project_state import ProjectState
from studio.core.time_utils import fmt_time
from studio.media.audio_source import AudioSourceCache
from studio.render.compositor import _blit_rgb, _load_image_rgb
from studio.render.playlist_forest_mist import draw_forest_mist_track_list
from studio.render.playlist_minimal_white import MINIMAL_WHITE_REF_CARD_W, draw_minimal_white_track_list
from studio.render.visualizer import _draw_bars, _draw_wave, _hex_to_rgb

_FontLoader = ImageFont.FreeTypeFont | ImageFont.ImageFont


def _font_for(typography, size_px: int) -> _FontLoader:
    return playlist_font_fn(typography.font_family)(size_px)


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


def _rgb(hex_color: str) -> tuple[int, int, int]:
    r, g, b, _a = _parse_hex(hex_color)
    return r, g, b


def _vertical_gradient(h: int, w: int, top: str, bottom: str) -> np.ndarray:
    c1 = np.array(_rgb(top), dtype=np.float32)
    c2 = np.array(_rgb(bottom), dtype=np.float32)
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, np.newaxis, np.newaxis]
    grad = c1 * (1.0 - t) + c2 * t
    return np.repeat(grad.astype(np.uint8), w, axis=1)


def _current_track(settings: PlaylistSettings, project_state: ProjectState, time: float) -> tuple[int, float]:
    elapsed = 0.0
    for index, media_id in enumerate(settings.song_ids):
        media = project_state.get_media(media_id)
        duration = float(media.duration or 0) if media else 0.0
        if duration <= 0:
            continue
        if time < elapsed + duration:
            return index, time - elapsed
        elapsed += duration
    if settings.song_ids:
        return len(settings.song_ids) - 1, 0.0
    return 0, 0.0


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    radius: int,
) -> None:
    draw.rounded_rectangle(box, radius=max(0, radius), fill=fill)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    trimmed = text
    while trimmed and draw.textlength(trimmed + "…", font=font) > max_w:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed else "…"


def _draw_cover(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    cover_path: str | None,
    accent: str,
    accent2: str,
    radius: int,
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    if cover_path:
        frame = _load_image_rgb(cover_path)
        if frame is not None:
            interp = cv2.INTER_AREA if (w < frame.shape[1] or h < frame.shape[0]) else cv2.INTER_LINEAR
            resized = cv2.resize(frame, (w, h), interpolation=interp)
            _blit_rgb(canvas, resized, x, y, 1.0)
            return
    patch = np.zeros((h, w, 3), dtype=np.uint8)
    c1 = np.array(_rgb(accent), dtype=np.float32)
    c2 = np.array(_rgb(accent2), dtype=np.float32)
    for row in range(h):
        t = row / max(1, h - 1)
        patch[row, :] = (c1 * (1 - t) + c2 * t).astype(np.uint8)
    _blit_rgb(canvas, patch, x, y, 1.0)


def _draw_text_block(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    lines: list[tuple[str, int, str]],
    *,
    font_family: str = "Segoe UI",
    surface: str | None = None,
    radius: int = 0,
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    img = Image.fromarray(canvas).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    box = (x, y, x + w, y + h)
    if surface:
        _draw_rounded_rect(draw, box, _parse_hex(surface), radius)
    cursor_y = y + 6
    for text, size_px, color in lines:
        if cursor_y >= y + h - 4:
            break
        font = playlist_font(font_family, size_px)
        line = _fit_text(draw, text, font, w - 12)
        draw.text((x + 6, cursor_y), line, font=font, fill=_parse_hex(color))
        cursor_y += int(size_px * 1.35)
    img = Image.alpha_composite(img, overlay)
    canvas[:] = np.array(img.convert("RGB"))


def _draw_waveform_in_rect(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    band_values,
    wave_values,
    c1: str,
    c2: str,
    surface: str,
    radius: int,
) -> None:
    x, y, w, h = rect
    if w <= 2 or h <= 2:
        return
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    _draw_rounded_rect(draw, (0, 0, w, h), _parse_hex(surface), radius)
    rgb1, rgb2 = _hex_to_rgb(c1), _hex_to_rgb(c2)
    if band_values is not None and len(band_values) > 0:
        _draw_bars(draw, np.asarray(band_values), w, h, rgb1, rgb2, mirror=False)
    elif wave_values is not None and len(wave_values) > 1:
        _draw_wave(draw, np.asarray(wave_values), w, h, rgb1, rgb2)
    patch = np.array(layer.convert("RGB"))
    alpha = np.array(layer.split()[-1], dtype=np.float32) / 255.0
    region = canvas[y : y + h, x : x + w].astype(np.float32)
    a = alpha[..., np.newaxis]
    blended = region * (1.0 - a) + patch.astype(np.float32) * a
    canvas[y : y + h, x : x + w] = blended.astype(np.uint8)


def _draw_progress(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    fraction: float,
    accent: str,
    muted: str,
    radius: int,
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    img = Image.fromarray(canvas).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    track = (x, y + h // 3, x + w, y + h - h // 3)
    _draw_rounded_rect(draw, track, _parse_hex(muted if len(muted) > 7 else "#44444488"), radius)
    fill_w = max(2, int(w * max(0.0, min(1.0, fraction))))
    fill = (x, y + h // 3, x + fill_w, y + h - h // 3)
    _draw_rounded_rect(draw, fill, _parse_hex(accent), radius)
    img = Image.alpha_composite(img, overlay)
    canvas[:] = np.array(img.convert("RGB"))


def _draw_background_cover(canvas: np.ndarray, image_path: str) -> bool:
    frame = _load_image_rgb(image_path)
    if frame is None:
        return False
    h, w = canvas.shape[:2]
    ih, iw = frame.shape[:2]
    if ih <= 0 or iw <= 0:
        return False
    scale = max(w / iw, h / ih)
    nw = max(1, int(round(iw * scale)))
    nh = max(1, int(round(ih * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(frame, (nw, nh), interpolation=interp)
    x0 = max(0, (nw - w) // 2)
    y0 = max(0, (nh - h) // 2)
    crop = resized[y0 : y0 + h, x0 : x0 + w]
    if crop.shape[0] == h and crop.shape[1] == w:
        canvas[:] = crop
        return True
    return False


def _log_song_list_render(
    settings: PlaylistSettings,
    canvas_w: int,
    canvas_h: int,
    norm: dict[str, float],
    px: tuple[int, int, int, int],
) -> None:
    from core.playlist_layout import is_forest_mist_layout, is_minimal_white_layout
    from core.preview_drag_log import log_render_rect

    ref_w: int | None = None
    ref_h: int | None = None
    if is_forest_mist_layout(settings):
        from render.playlist_forest_mist import FOREST_MIST_REF_CARD_W, forest_mist_card_height

        ref_w = FOREST_MIST_REF_CARD_W
        ref_h = forest_mist_card_height(settings, settings.typography, ref_w)
    elif is_minimal_white_layout(settings):
        from render.playlist_minimal_white import minimal_white_card_height

        ref_w = MINIMAL_WHITE_REF_CARD_W
        ref_h = minimal_white_card_height(settings, settings.typography, ref_w)

    log_render_rect(
        sub_template=settings.sub_template_id or "",
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        norm=norm,
        px=px,
        ref_w=ref_w,
        ref_h=ref_h,
    )


def _draw_song_list_card(
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
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return

    typo = settings.typography

    sub = SUB_TEMPLATES_BY_ID.get(settings.sub_template_id or "")
    if sub is not None and sub.layout_style == "minimal_white":
        ch, cw = canvas.shape[:2]
        draw_minimal_white_track_list(
            canvas,
            rect,
            settings=settings,
            project_state=project_state,
            current_index=current_index,
            local_time=local_time,
            playback_time=playback_time,
            band_values=band_values,
            colors=colors,
            radius=radius,
            font_fn=playlist_font_fn(typo.font_family),
            canvas_w=cw,
            canvas_h=ch,
        )
        return

    if sub is not None and sub.layout_style == "forest_mist":
        ch, cw = canvas.shape[:2]
        draw_forest_mist_track_list(
            canvas,
            rect,
            settings=settings,
            project_state=project_state,
            current_index=current_index,
            local_time=local_time,
            playback_time=playback_time,
            band_values=band_values,
            colors=colors,
            radius=radius,
            font_fn=playlist_font_fn(typo.font_family),
            canvas_w=cw,
            canvas_h=ch,
        )
        return

    glass = sub.glass if sub is not None else False
    neon = sub.neon_border if sub is not None else False

    surface = colors.get("surface", "#ffffff22")
    text_color = colors.get("text", "#ffffff")
    muted = colors.get("muted", "#aaaaaa")
    accent = colors.get("accent", "#7466F1")
    selected_row = colors.get("selected_row", "#7466F144")

    img = Image.fromarray(canvas).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    card = (x, y, x + w, y + h)
    fill = _parse_hex(surface)
    if glass:
        fill = (fill[0], fill[1], fill[2], min(fill[3], 140))
    _draw_rounded_rect(draw, card, fill, radius)
    if neon:
        draw.rounded_rectangle(card, radius=radius, outline=_parse_hex(accent), width=2)

    header_font = _font_for(typo, max(10, typo.song_meta_size))
    draw.text((x + 12, y + 10), "TRACK LIST", font=header_font, fill=_parse_hex(text_color))

    row_gap = max(2, settings.list_row_gap)
    row_h = max(18, typo.song_title_size + 6)
    y_cursor = y + 10 + int(typo.song_meta_size * 1.8)
    max_rows = max(1, (y + h - y_cursor - 28) // (row_h + row_gap))

    songs = settings.song_ids[:max_rows]
    if not songs:
        draw.text(
            (x + 12, y_cursor),
            "No songs in playlist",
            font=_font_for(typo, typo.song_meta_size),
            fill=_parse_hex(muted),
        )
    else:
        for index, media_id in enumerate(songs):
            media = project_state.get_media(media_id)
            if media is None:
                continue
            row_y = y_cursor + index * (row_h + row_gap)
            row_box = (x + 8, row_y, x + w - 8, row_y + row_h)
            if index == current_index:
                _draw_rounded_rect(draw, row_box, _parse_hex(selected_row), max(4, radius // 3))
            num_font = _font_for(typo, typo.song_meta_size)
            title_font = _font_for(
                typo,
                typo.song_title_size if index == current_index else typo.song_meta_size,
            )
            num = f"{index + 1:02d}" if settings.show_track_numbers else ""
            if num:
                draw.text((row_box[0] + 6, row_y + 4), num, font=num_font, fill=_parse_hex(accent if index == current_index else muted))
            title_x = row_box[0] + (32 if settings.show_track_numbers else 6)
            title = _fit_text(draw, media.name, title_font, row_box[2] - title_x - 48)
            draw.text(
                (title_x, row_y + 4),
                title,
                font=title_font,
                fill=_parse_hex(accent if index == current_index else text_color),
            )
            if settings.show_durations:
                dur = fmt_time(media.duration or 0)
                dur_w = draw.textlength(dur, font=num_font)
                draw.text(
                    (row_box[2] - dur_w - 6, row_y + 4),
                    dur,
                    font=num_font,
                    fill=_parse_hex(muted),
                )

    footer_font = _font_for(typo, max(9, typo.song_meta_size - 1))
    footer = "VIEW FULL PLAYLIST →"
    footer_w = draw.textlength(footer, font=footer_font)
    draw.text(
        (x + (w - footer_w) / 2, y + h - 22),
        footer,
        font=footer_font,
        fill=_parse_hex(muted),
    )

    img = Image.alpha_composite(img, overlay)
    canvas[:] = np.array(img.convert("RGB"))


def _build_playlist_background(
    width: int,
    height: int,
    *,
    colors: dict[str, str],
    bg_path: str | None,
) -> np.ndarray:
    """Gradient fallback; bundled ``assets/playlist_templates/*/background.png`` when present."""
    bg_from = colors.get("bg_from", "#0a1020")
    bg_to = colors.get("bg_to", "#050810")
    canvas = _vertical_gradient(height, width, bg_from, bg_to)
    if bg_path:
        mtime = background_mtime_ns(bg_path)
        cover = cached_background_cover(bg_path, width, height, mtime)
        if cover is not None:
            canvas[:] = cover
    return canvas


def _playlist_render_context(
    project_state: ProjectState,
    canvas: np.ndarray,
    time: float,
    audio_cache: AudioSourceCache | None,
) -> dict | None:
    settings = project_state.project.playlist
    if not settings.template_id:
        return None

    height, width = canvas.shape[:2]
    standalone = is_standalone_track_list_layout(settings)
    colors = resolve_playlist_colors(settings)
    if not standalone and settings.colors:
        colors = {**colors, **settings.colors}

    layout = resolve_component_layout(settings, canvas_w=width, canvas_h=height)
    typo = settings.typography
    current_index, local_time = _current_track(settings, project_state, time)

    band_values = None
    wave_values = None
    if (
        audio_cache is not None
        and settings.song_ids
        and getattr(project_state, "is_playing", False)
    ):
        media_id = settings.song_ids[min(current_index, len(settings.song_ids) - 1)]
        media = project_state.get_media(media_id)
        if media is not None:
            source = audio_cache.get(media.id, media.path, media.type)
            if source is not None:
                band_values = source.get_spectrum_bands(local_time)
                wave_values = source.get_waveform_samples(local_time)

    return {
        "settings": settings,
        "width": width,
        "height": height,
        "standalone": standalone,
        "colors": colors,
        "layout": layout,
        "typo": typo,
        "current_index": current_index,
        "local_time": local_time,
        "band_values": band_values,
        "wave_values": wave_values,
        "time": time,
    }


def draw_playlist_background(canvas: np.ndarray, project_state: ProjectState) -> None:
    """Paint only the playlist scene background (gradient or image)."""
    settings = project_state.project.playlist
    if not settings.template_id:
        return

    height, width = canvas.shape[:2]
    standalone = is_standalone_track_list_layout(settings)
    colors = resolve_playlist_colors(settings)
    if not standalone and settings.colors:
        colors = {**colors, **settings.colors}

    bg_from = colors.get("bg_from", "#0a1020")
    bg_to = colors.get("bg_to", "#050810")
    bg_path_obj = resolve_playlist_background(settings)
    bg_path = str(bg_path_obj) if bg_path_obj is not None else None
    bg_key = playlist_background_key(width, height, bg_path, bg_from, bg_to)
    canvas[:] = playlist_render_cache().get_background(
        bg_key,
        lambda: _build_playlist_background(
            width,
            height,
            colors=colors,
            bg_path=bg_path,
        ),
    )


def draw_playlist_foreground(
    canvas: np.ndarray,
    project_state: ProjectState,
    time: float,
    audio_cache: AudioSourceCache | None = None,
) -> None:
    """Paint playlist card components (cover, song list, waveform, …) without background."""
    ctx = _playlist_render_context(project_state, canvas, time, audio_cache)
    if ctx is None:
        return

    settings = ctx["settings"]
    width = ctx["width"]
    height = ctx["height"]
    standalone = ctx["standalone"]
    colors = ctx["colors"]
    layout = ctx["layout"]
    typo = ctx["typo"]
    current_index = ctx["current_index"]
    local_time = ctx["local_time"]
    band_values = ctx["band_values"]
    wave_values = ctx["wave_values"]

    surface = colors.get("surface", "#ffffff22")
    accent = colors.get("accent", "#7466F1")
    accent2 = colors.get("accent2", "#A259FF")
    text_color = colors.get("text", "#ffffff")
    muted = colors.get("muted", "#aaaaaa")

    for comp_id in settings.component_order:
        if comp_id not in PLAYLIST_COMPONENTS:
            continue
        if standalone and comp_id != "song_list":
            continue
        rect = layout.get(comp_id)
        if not rect:
            continue
        px = rect_to_pixels(rect, width, height)
        radius = settings.corner_radius

        if comp_id == "cover":
            _draw_cover(canvas, px, settings.cover_path, accent, accent2, radius)
        elif comp_id == "title":
            title = settings.album_title or "Untitled Album"
            _draw_text_block(
                canvas,
                px,
                [(title, typo.album_title_size, text_color)],
                font_family=typo.font_family,
                surface=surface,
                radius=radius,
            )
        elif comp_id == "now_playing":
            if settings.song_ids:
                media = project_state.get_media(settings.song_ids[current_index])
                label = media.name if media else "Now playing"
            else:
                label = "Add songs to preview"
            _draw_text_block(
                canvas,
                px,
                [("NOW PLAYING", typo.song_meta_size, muted), (label, typo.now_playing_size, accent)],
                font_family=typo.font_family,
                surface=surface,
                radius=radius,
            )
        elif comp_id == "song_list":
            _log_song_list_render(settings, width, height, rect, px)
            _draw_song_list_card(
                canvas,
                px,
                settings=settings,
                project_state=project_state,
                current_index=current_index,
                local_time=local_time,
                playback_time=time,
                band_values=band_values,
                colors=colors,
                radius=radius,
            )
        elif comp_id == "waveform":
            _draw_waveform_in_rect(canvas, px, band_values, wave_values, accent, accent2, surface, radius)
        elif comp_id == "progress":
            media = None
            if settings.song_ids:
                media = project_state.get_media(settings.song_ids[current_index])
            duration = float(media.duration or 1.0) if media else 1.0
            fraction = local_time / duration if duration > 0 else 0.0
            _draw_progress(canvas, px, fraction, accent, muted, radius)


def draw_playlist(
    canvas: np.ndarray,
    project_state: ProjectState,
    time: float,
    audio_cache: AudioSourceCache | None = None,
) -> None:
    """Composite playlist template onto ``canvas`` (HxWx3 RGB, in place)."""
    draw_playlist_background(canvas, project_state)
    draw_playlist_foreground(canvas, project_state, time, audio_cache=audio_cache)
