"""Default and resolved layout rects for playlist template components."""

from __future__ import annotations

import inspect

from studio.core.playlist_settings import PLAYLIST_COMPONENTS, PlaylistSettings
from studio.core.playlist_sub_templates import SUB_TEMPLATES_BY_ID

Rect = dict[str, float]  # x, y, w, h — normalized 0..1

# Reference card proportions (1280×720 canvas) — width derived from height so the
# card stays the same shape at every window size / aspect ratio.
MINIMAL_WHITE_REF_CARD_W = 380
MINIMAL_WHITE_REF_CARD_H = 650
MINIMAL_WHITE_CARD_ASPECT = MINIMAL_WHITE_REF_CARD_W / MINIMAL_WHITE_REF_CARD_H
_MINIMAL_WHITE_CARD_H = 0.90
_MINIMAL_WHITE_MARGIN_X = 0.06
_MINIMAL_WHITE_CARD_Y = 0.05
_MINIMAL_WHITE_MAX_WIDTH = 0.42


def _minimal_white_card_width_norm(canvas_w: int, canvas_h: int) -> float:
    """Card width on canvas — fixed; only height shrinks with track count."""
    if canvas_w <= 0 or canvas_h <= 0:
        return 0.44
    pixel_h = _MINIMAL_WHITE_CARD_H * canvas_h
    pixel_w = pixel_h * MINIMAL_WHITE_CARD_ASPECT
    norm_w = pixel_w / canvas_w
    if norm_w > _MINIMAL_WHITE_MAX_WIDTH:
        norm_w = _MINIMAL_WHITE_MAX_WIDTH
    return round(norm_w, 4)


def _minimal_white_card_size_norm(
    canvas_w: int,
    canvas_h: int,
    settings: PlaylistSettings | None = None,
) -> tuple[float, float]:
    """Return (norm_w, norm_h). Width stays full; height fits the track list."""
    if canvas_w <= 0 or canvas_h <= 0:
        return 0.44, _MINIMAL_WHITE_CARD_H

    norm_w = _minimal_white_card_width_norm(canvas_w, canvas_h)
    norm_h = _MINIMAL_WHITE_CARD_H

    if settings is not None and is_standalone_track_list_layout(settings):
        if is_forest_mist_layout(settings):
            from studio.render.playlist_forest_mist import FOREST_MIST_REF_CARD_W, forest_mist_card_height

            ideal_px = forest_mist_card_height(settings, settings.typography, FOREST_MIST_REF_CARD_W)
        elif is_emotional_music_layout(settings):
            from studio.render.playlist_emotional_music import EMOTIONAL_REF_CARD_W, emotional_music_card_height

            ideal_px = emotional_music_card_height(settings, settings.typography, EMOTIONAL_REF_CARD_W)
        else:
            from studio.render.playlist_minimal_white import minimal_white_card_height

            ideal_px = minimal_white_card_height(settings, settings.typography, MINIMAL_WHITE_REF_CARD_W)
        norm_h = min(_MINIMAL_WHITE_CARD_H + 0.02, ideal_px / canvas_h)
        norm_h = max(0.18, norm_h)

    return norm_w, round(norm_h, 4)


def _minimal_white_layout(settings: PlaylistSettings, *, canvas_w: int = 1280, canvas_h: int = 720) -> dict[str, Rect]:
    norm_w, norm_h = _minimal_white_card_size_norm(canvas_w, canvas_h, settings)
    if settings.list_side == "left":
        x = _MINIMAL_WHITE_MARGIN_X
    else:
        x = round(1.0 - _MINIMAL_WHITE_MARGIN_X - norm_w, 4)
    return {
        "song_list": {
            "x": x,
            "y": _MINIMAL_WHITE_CARD_Y,
            "w": norm_w,
            "h": norm_h,
        }
    }


def is_minimal_white_layout(settings: PlaylistSettings) -> bool:
    sub = SUB_TEMPLATES_BY_ID.get(settings.sub_template_id or "")
    return sub is not None and sub.layout_style == "minimal_white"


def is_forest_mist_layout(settings: PlaylistSettings) -> bool:
    sub = SUB_TEMPLATES_BY_ID.get(settings.sub_template_id or "")
    return sub is not None and sub.layout_style == "forest_mist"


def is_emotional_music_layout(settings: PlaylistSettings) -> bool:
    sub = SUB_TEMPLATES_BY_ID.get(settings.sub_template_id or "")
    return sub is not None and sub.layout_style == "emotional_music"


def is_standalone_track_list_layout(settings: PlaylistSettings) -> bool:
    sub = SUB_TEMPLATES_BY_ID.get(settings.sub_template_id or "")
    return sub is not None and sub.layout_style in ("minimal_white", "forest_mist", "emotional_music")


_RIGHT_LAYOUT: dict[str, Rect] = {
    "cover": {"x": 0.04, "y": 0.06, "w": 0.36, "h": 0.88},
    "title": {"x": 0.44, "y": 0.05, "w": 0.52, "h": 0.08},
    "now_playing": {"x": 0.44, "y": 0.14, "w": 0.52, "h": 0.10},
    "song_list": {"x": 0.44, "y": 0.26, "w": 0.52, "h": 0.48},
    "waveform": {"x": 0.44, "y": 0.76, "w": 0.52, "h": 0.12},
    "progress": {"x": 0.44, "y": 0.90, "w": 0.52, "h": 0.04},
}


def _mirror_layout(layout: dict[str, Rect]) -> dict[str, Rect]:
    mirrored: dict[str, Rect] = {}
    for key, rect in layout.items():
        mirrored[key] = {
            "x": round(1.0 - rect["x"] - rect["w"], 4),
            "y": rect["y"],
            "w": rect["w"],
            "h": rect["h"],
        }
    return mirrored


def default_component_layout(settings: PlaylistSettings) -> dict[str, Rect]:
    base = _RIGHT_LAYOUT if settings.list_side != "left" else _mirror_layout(_RIGHT_LAYOUT)
    cover_w = max(0.18, min(0.55, settings.cover_size_pct / 100.0 * 0.42))
    base = {k: dict(v) for k, v in base.items()}
    base["cover"]["w"] = cover_w
    if settings.list_side == "left":
        base["cover"]["x"] = 1.0 - 0.04 - cover_w
        content_x = 0.04
    else:
        base["cover"]["x"] = 0.04
        content_x = 0.04 + cover_w + 0.04
    content_w = max(0.2, 0.92 - cover_w - 0.08)
    for key in ("title", "now_playing", "song_list", "waveform", "progress"):
        if key in base:
            base[key]["x"] = content_x
            base[key]["w"] = content_w
    return base


def standalone_song_list_rect_norm(
    settings: PlaylistSettings,
    *,
    canvas_w: int,
    canvas_h: int,
    x: float | None = None,
    y: float | None = None,
) -> Rect:
    """Norm rect sized to the template's intrinsic card dimensions (stable aspect ratio)."""
    from studio.core.time_utils import clamp

    if canvas_w <= 0 or canvas_h <= 0:
        return {"x": 0.06, "y": 0.05, "w": 0.44, "h": 0.90}

    if is_forest_mist_layout(settings):
        from studio.render.playlist_forest_mist import FOREST_MIST_REF_CARD_W, forest_mist_card_height

        ref_w = FOREST_MIST_REF_CARD_W
        ref_h = forest_mist_card_height(settings, settings.typography, ref_w)
    elif is_emotional_music_layout(settings):
        from studio.render.playlist_emotional_music import EMOTIONAL_REF_CARD_W, emotional_music_card_height

        ref_w = EMOTIONAL_REF_CARD_W
        ref_h = emotional_music_card_height(settings, settings.typography, ref_w)
    else:
        from studio.render.playlist_minimal_white import minimal_white_card_height

        ref_w = MINIMAL_WHITE_REF_CARD_W
        ref_h = minimal_white_card_height(settings, settings.typography, ref_w)

    norm_w = min(ref_w / canvas_w, 0.95)
    norm_h = min(ref_h / canvas_h, 0.95)
    base = _minimal_white_layout(settings, canvas_w=canvas_w, canvas_h=canvas_h)["song_list"]
    if x is not None:
        out_x = float(x)
    elif settings.list_side == "left":
        out_x = _MINIMAL_WHITE_MARGIN_X
    else:
        # Keep a fixed proportional gap from the edge, measured from the actual
        # card width used — so wider cards (Emotional Music) don't slide flush
        # against the right edge like the old aspect-derived base did.
        out_x = round(1.0 - _MINIMAL_WHITE_MARGIN_X - norm_w, 4)
    out_y = base["y"] if y is None else float(y)
    out_x = clamp(out_x, 0.0, 1.0 - norm_w)
    out_y = clamp(out_y, 0.0, 1.0 - norm_h)
    return {
        "x": round(out_x, 4),
        "y": round(out_y, 4),
        "w": round(norm_w, 4),
        "h": round(norm_h, 4),
    }


def resolve_component_layout(
    settings: PlaylistSettings,
    *,
    canvas_w: int | None = None,
    canvas_h: int | None = None,
) -> dict[str, Rect]:
    if is_standalone_track_list_layout(settings):
        cw = canvas_w if canvas_w and canvas_w > 0 else 1280
        ch = canvas_h if canvas_h and canvas_h > 0 else 720
        custom = settings.component_layout.get("song_list")
        caller = inspect.stack()[1].function
        if custom and "w" in custom and "h" in custom:
            merged = standalone_song_list_rect_norm(
                settings,
                canvas_w=cw,
                canvas_h=ch,
                x=float(custom.get("x", _minimal_white_layout(settings, canvas_w=cw, canvas_h=ch)["song_list"]["x"])),
                y=float(custom.get("y", _minimal_white_layout(settings, canvas_w=cw, canvas_h=ch)["song_list"]["y"])),
            )
            merged["w"] = float(custom["w"])
            merged["h"] = float(custom["h"])
            merged["x"] = float(custom.get("x", merged["x"]))
            merged["y"] = float(custom.get("y", merged["y"]))
            _log_standalone_resolve(settings, cw, ch, custom, merged, caller)
            return {"song_list": merged}
        if custom and ("x" in custom or "y" in custom):
            resolved = standalone_song_list_rect_norm(
                settings,
                canvas_w=cw,
                canvas_h=ch,
                x=float(custom["x"]) if "x" in custom else None,
                y=float(custom["y"]) if "y" in custom else None,
            )
            _log_standalone_resolve(settings, cw, ch, custom, resolved, caller)
            return {"song_list": resolved}
        resolved = standalone_song_list_rect_norm(settings, canvas_w=cw, canvas_h=ch)
        _log_standalone_resolve(settings, cw, ch, custom, resolved, caller)
        return {"song_list": resolved}

    defaults = default_component_layout(settings)
    resolved = dict(defaults)
    for comp_id, rect in settings.component_layout.items():
        if comp_id not in PLAYLIST_COMPONENTS:
            continue
        merged = dict(defaults.get(comp_id, {}))
        merged.update({k: float(v) for k, v in rect.items() if k in ("x", "y", "w", "h")})
        resolved[comp_id] = merged
    return resolved


def _log_standalone_resolve(
    settings: PlaylistSettings,
    canvas_w: int,
    canvas_h: int,
    custom: dict[str, float] | None,
    resolved: Rect,
    caller: str,
) -> None:
    from studio.core.preview_drag_log import log_layout_resolve

    log_layout_resolve(
        sub_template=settings.sub_template_id or "",
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        custom=custom,
        resolved=resolved,
        caller=caller,
    )


def rect_to_pixels(rect: Rect, width: int, height: int) -> tuple[int, int, int, int]:
    x = int(round(rect["x"] * width))
    y = int(round(rect["y"] * height))
    w = max(1, int(round(rect["w"] * width)))
    h = max(1, int(round(rect["h"] * height)))
    return x, y, w, h
