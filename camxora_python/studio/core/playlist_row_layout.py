"""Compute track-row chrome geometry (numbers, play, duration, animation)."""

from __future__ import annotations

from dataclasses import dataclass

from studio.core.playlist_row_chrome import (
    DEFAULT_NUM_COLUMN_W,
    ROW_INSET_X,
    PlaylistRowChrome,
    RowAnimationStyle,
    RowPlayStyle,
)
from PIL import ImageDraw, ImageFont


@dataclass(frozen=True)
class RowTextLayout:
    title_y: int
    artist_y: int | None
    num_y: int
    dur_y: int


@dataclass(frozen=True)
class RowLayoutPlan:
    inset_x: int
    text_x: int
    text_w: int
    show_number: bool
    number_x: int
    show_play: bool
    play_cx: int
    play_cy: int
    play_r: int
    show_animation: bool
    animation_x: int
    animation_y: int
    animation_total_w: int
    show_duration: bool
    duration_x: int
    text_layout: RowTextLayout


def text_y_center(font: ImageFont.ImageFont, row_y: int, row_h: int) -> int:
    try:
        ascent, descent = font.getmetrics()
        text_h = ascent + descent
    except Exception:
        text_h = 14
    return row_y + max(0, (row_h - text_h) // 2)


def text_block_origin(
    row_y: int,
    row_h: int,
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    *,
    line_gap: int = 2,
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


def compute_row_text_layout(
    row_y: int,
    row_h: int,
    *,
    title_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    num_font: ImageFont.ImageFont,
    artist: str | None,
) -> RowTextLayout:
    if artist:
        title_y, artist_y = text_block_origin(row_y, row_h, title_font, meta_font)
        num_y = text_y_center(num_font, row_y, row_h)
        dur_y = text_y_center(meta_font, row_y, row_h)
        return RowTextLayout(title_y=title_y, artist_y=artist_y, num_y=num_y, dur_y=dur_y)
    line_y = text_y_center(title_font, row_y, row_h)
    num_y = text_y_center(num_font, row_y, row_h)
    dur_y = text_y_center(meta_font, row_y, row_h)
    return RowTextLayout(title_y=line_y, artist_y=None, num_y=num_y, dur_y=dur_y)


def animation_total_width(anim: RowAnimationStyle) -> int:
    n = anim.bar_count
    if n <= 0:
        return 0
    return n * anim.bar_width_px + max(0, n - 1) * anim.bar_gap_px


def _play_in_num_column(chrome: PlaylistRowChrome, *, playing: bool) -> bool:
    play = chrome.play
    return bool(
        playing
        and play.enabled
        and play.placement == "leading"
        and not play.show_on_inactive
        and play.when_playing in ("play_icon", "both")
    )


def _reserve_num_column(chrome: PlaylistRowChrome, *, playing: bool) -> bool:
    """Keep number column width even when the play icon occupies that slot."""
    if not chrome.numbers.enabled:
        return False
    if _play_in_num_column(chrome, playing=playing):
        return True
    return chrome.numbers.enabled


def _show_number_text(chrome: PlaylistRowChrome, *, playing: bool) -> bool:
    if not chrome.numbers.enabled:
        return False
    play = chrome.play
    if (
        playing
        and play.enabled
        and play.placement == "leading"
        and not play.show_on_inactive
        and play.when_playing in ("play_icon", "both")
    ):
        return False
    return True


def _leading_mode(chrome: PlaylistRowChrome, *, playing: bool) -> str | None:
    play = chrome.play
    anim = chrome.animation
    if playing:
        when = play.when_playing
        if when == "hide":
            return None
        if when == "animation":
            return "animation" if anim.enabled and anim.placement == "leading" else None
        if when == "play_icon":
            return "play" if play.enabled and play.placement == "leading" else None
        if when == "both":
            if play.enabled and play.placement == "leading":
                return "play"
            if anim.enabled and anim.placement == "leading":
                return "animation"
            return None
    if play.enabled and play.show_on_inactive and play.placement == "leading":
        return "play"
    return None


def _trailing_animation(chrome: PlaylistRowChrome, *, playing: bool) -> bool:
    anim = chrome.animation
    return bool(playing and anim.enabled and anim.placement == "trailing")


def compute_row_layout(
    *,
    row_x0: int,
    row_x1: int,
    row_y: int,
    row_h: int,
    chrome: PlaylistRowChrome,
    playing: bool,
    duration_label: str,
    draw: ImageDraw.ImageDraw,
    meta_font: ImageFont.ImageFont,
    play_r: int,
    title_font: ImageFont.ImageFont,
    num_font: ImageFont.ImageFont,
    artist: str | None,
    inset_x: int = ROW_INSET_X,
    text_gap: int = 10,
    trailing_gap: int = 8,
) -> RowLayoutPlan:
    text_layout = compute_row_text_layout(
        row_y,
        row_h,
        title_font=title_font,
        meta_font=meta_font,
        num_font=num_font,
        artist=artist,
    )

    reserve_num_col = _reserve_num_column(chrome, playing=playing)
    show_number = _show_number_text(chrome, playing=playing)
    num_col_w = chrome.numbers.column_width_px if reserve_num_col or show_number else 0

    leading = _leading_mode(chrome, playing=playing)
    anim = chrome.animation
    anim_w = animation_total_width(anim) if leading == "animation" else 0
    if _trailing_animation(chrome, playing=playing):
        trailing_anim_w = animation_total_width(anim)
    else:
        trailing_anim_w = 0

    play_w = play_r * 2
    play_in_num = _play_in_num_column(chrome, playing=playing)

    cursor = row_x0 + inset_x
    number_x = cursor
    if reserve_num_col or show_number:
        cursor += num_col_w

    if play_in_num:
        play_cx = row_x0 + inset_x + num_col_w // 2
    elif leading == "play":
        play_cx = cursor + play_r
    else:
        play_cx = cursor
    play_cy = row_y + row_h // 2

    if play_in_num:
        text_x = row_x0 + inset_x + num_col_w
    elif leading == "play":
        text_x = cursor + play_w + text_gap
    elif leading == "animation":
        text_x = cursor + anim_w + text_gap
    else:
        text_x = cursor

    right = row_x1 - inset_x
    dur_w = int(draw.textlength(duration_label, font=meta_font)) if duration_label and chrome.duration.enabled else 0
    show_duration = bool(duration_label and chrome.duration.enabled)
    show_trailing_anim = trailing_anim_w > 0

    bar_x = None
    dur_x = None
    if show_trailing_anim:
        bar_x = right - trailing_anim_w
    if show_duration:
        if chrome.duration.placement == "before_animation" and show_trailing_anim and bar_x is not None:
            dur_x = bar_x - trailing_gap - dur_w
        else:
            dur_x = right - dur_w - (trailing_anim_w + trailing_gap if show_trailing_anim else 0)

    text_right = right
    if dur_x is not None:
        text_right = min(text_right, dur_x - 4)
    elif bar_x is not None:
        text_right = min(text_right, bar_x - 4)
    text_w = max(40, text_right - text_x)

    animation_x = bar_x if bar_x is not None else (cursor if leading == "animation" else 0)
    animation_y = row_y + row_h // 2 - anim.height_px // 2

    return RowLayoutPlan(
        inset_x=inset_x,
        text_x=text_x,
        text_w=text_w,
        show_number=show_number,
        number_x=number_x,
        show_play=leading == "play" and chrome.play.enabled and chrome.play.shape != "none",
        play_cx=play_cx,
        play_cy=play_cy,
        play_r=play_r,
        show_animation=(leading == "animation" and anim_w > 0)
        or show_trailing_anim,
        animation_x=animation_x if show_trailing_anim else (cursor if leading == "animation" else animation_x),
        animation_y=animation_y,
        animation_total_w=trailing_anim_w if show_trailing_anim else anim_w,
        show_duration=show_duration and dur_x is not None,
        duration_x=dur_x or 0,
        text_layout=text_layout,
    )
