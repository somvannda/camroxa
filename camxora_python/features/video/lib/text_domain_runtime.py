"""Expand albumText / titleText template blocks into drawable textOverlays."""

from __future__ import annotations

from typing import Any

from features.video.lib.template_value_utils import normalize_color
from features.video.lib.text_domain_registry import (
    normalize_album_text_settings,
    normalize_title_text_settings,
)
from features.video.lib.track_display_name import format_title_marker, track_titles_from_paths


def _style_num(style: dict[str, Any], key: str, default: float) -> float:
    """Read a numeric style field — preserves explicit 0 (unlike ``x or default``)."""
    if key not in style or style.get(key) is None:
        return float(default)
    try:
        return float(style.get(key))
    except (TypeError, ValueError):
        return float(default)


def _style_to_overlay_fields(style: dict[str, Any]) -> dict[str, Any]:
    gradient = style.get("gradientColors")
    gradient_colors = list(gradient) if isinstance(gradient, list) else []
    return {
        "sizePx": float(max(5.0, _style_num(style, "fontSize", 10.0))),
        "fontFamily": str(style.get("fontFamily") or "arial"),
        "bold": bool(style.get("bold", False)),
        "italic": bool(style.get("italic", False)),
        "color": str(style.get("color") or "#ffffff"),
        "fillMode": str(style.get("fillMode") or "solid"),
        "gradientColors": gradient_colors,
        "gradientDirection": str(style.get("gradientDirection") or "vertical"),
        "glowColor": str(style.get("glowColor") or "#ff4fd8"),
        "glowMode": str(style.get("glowMode") or "solid"),
        "glowGradientColors": list(style.get("glowGradientColors") or [])
        if isinstance(style.get("glowGradientColors"), list)
        else [],
        "glowGradientDirection": str(style.get("glowGradientDirection") or "horizontal"),
        "strokeColor": str(style.get("strokeColor") or "#000000"),
        # Critical: ``0 or 2`` must NOT become 2 — zero means off.
        "strokeWidth": float(max(0.0, _style_num(style, "strokeWidth", 0.0))),
        "shadow": float(max(0.0, min(1.0, _style_num(style, "shadow", 0.0)))),
        "shadowBlur": float(max(0.0, _style_num(style, "shadowBlur", 0.0))),
        "glow": float(max(0.0, min(1.0, _style_num(style, "glow", 0.0)))),
        "glowBlur": float(max(0.0, _style_num(style, "glowBlur", 8.0))),
        "extrudeDepth": float(max(0.0, _style_num(style, "extrudeDepth", 0.0))),
        "extrudeColor": str(style.get("extrudeColor") or "#1a1a1a"),
        "letterSpacing": float(_style_num(style, "letterSpacing", 0.0)),
        "lineSpacing": float(max(0.8, _style_num(style, "lineSpacing", 1.2))),
        "boxWidth": float(max(0.0, _style_num(style, "boxWidth", 0.0))),
        "align": str(style.get("align") or "left"),
        "opacity": float(max(0.0, min(1.0, _style_num(style, "opacity", 1.0)))),
        "anchor": str(style.get("anchor") or "top-left"),
        "x": float(_style_num(style, "x", 0.0)),
        "y": float(_style_num(style, "y", 0.0)),
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def _load_measure_font(font_family: str, font_size: float, *, bold: bool = False, text: str = ""):
    """Best-effort PIL font matching the GPU text path (system fonts)."""
    from PIL import ImageFont

    from features.video.lib.system_fonts import resolve_font_for_text, resolve_font_file

    size = int(max(5, min(400, round(float(font_size or 16)))))
    if text:
        path = resolve_font_for_text(str(font_family or "arial"), text, bold=bool(bold))
    else:
        path = resolve_font_file(str(font_family or "arial"), bold=bool(bold))
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()


def measure_text_width_px(
    text: str,
    *,
    font_size: float,
    font_family: str = "arial",
    bold: bool = False,
    stroke_width: float = 0.0,
    letter_spacing: float = 0.0,
) -> float:
    """Measure rendered text width in template units (matches GPU glyph path)."""
    from PIL import Image, ImageDraw

    from features.video.lib.system_fonts import text_needs_complex_shaping

    raw = str(text or "")
    if not raw.strip():
        return 0.0
    font = _load_measure_font(font_family, font_size, bold=bold, text=raw)
    sw = int(max(0, min(24, round(float(stroke_width or 0)))))
    complex_script = text_needs_complex_shaping(raw)
    tracking = 0.0 if complex_script else float(letter_spacing or 0.0)
    draw = ImageDraw.Draw(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
    max_w = 0.0
    for line in raw.split("\n"):
        if not line:
            continue
        if abs(tracking) > 0.01:
            x = 0.0
            for ch in line:
                bbox = draw.textbbox((0, 0), ch, font=font, stroke_width=sw)
                x += float(max(1, bbox[2] - bbox[0])) + tracking
            max_w = max(max_w, x - tracking)
        else:
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=sw)
            max_w = max(max_w, float(max(1, bbox[2] - bbox[0])))
    # Soft bleed only when stroke is present (avoid inflating the CapCut frame).
    bleed = float(max(0.0, stroke_width or 0.0)) * 0.5
    return float(max_w + bleed)


def wrap_text_to_box_width(
    text: str,
    *,
    box_width: float,
    font_size: float,
    letter_spacing: float = 0.0,
    font_family: str = "arial",
    bold: bool = False,
    stroke_width: float = 0.0,
) -> str:
    """Soft-wrap ``text`` to fit ``box_width`` using real glyph measurements."""
    from features.video.lib.system_fonts import text_needs_complex_shaping

    raw = str(text or "")
    width = float(box_width or 0.0)
    if width <= 8.0 or not raw.strip():
        return raw
    size = float(max(5.0, font_size or 16.0))
    complex_script = text_needs_complex_shaping(raw)
    tracking = 0.0 if complex_script else float(letter_spacing or 0.0)
    family = str(font_family or "arial")
    is_bold = bool(bold)
    sw = float(max(0.0, stroke_width or 0.0))

    def line_w(sample: str) -> float:
        return measure_text_width_px(
            sample,
            font_size=size,
            font_family=family,
            bold=is_bold,
            stroke_width=sw,
            letter_spacing=tracking,
        )

    out_lines: list[str] = []
    for paragraph in raw.split("\n"):
        if not paragraph.strip():
            out_lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if line_w(candidate) <= width + 0.5:
                current = candidate
                continue
            if current:
                out_lines.append(current)
            # Hard-break overlong tokens by measured width.
            if line_w(word) <= width + 0.5:
                current = word
                continue
            if complex_script:
                # Do not split Khmer/complex clusters mid-word; keep the token
                # on its own line even if slightly wider than the box.
                current = word
                continue
            chunk = ""
            for ch in word:
                trial = chunk + ch
                if chunk and line_w(trial) > width + 0.5:
                    out_lines.append(chunk)
                    chunk = ch
                else:
                    chunk = trial
            current = chunk
        if current or not words:
            out_lines.append(current)
    return "\n".join(out_lines)


def resolve_album_display_text(
    album_settings: dict[str, Any],
    *,
    pipeline_album: str = "",
) -> str:
    mode = str(album_settings.get("contentMode") or "pipeline").lower()
    manual = str(album_settings.get("manualText") or "").strip()
    if mode == "manual":
        return manual
    pipeline = str(pipeline_album or "").strip()
    return pipeline or manual


def resolve_title_display_list(
    title_settings: dict[str, Any],
    *,
    track_paths: list[str] | None = None,
) -> list[str]:
    mode = str(title_settings.get("contentMode") or "pipeline").lower()
    manual = title_settings.get("manualTitles")
    manual_list = [str(item).strip() for item in manual] if isinstance(manual, list) else []
    manual_list = [item for item in manual_list if item]
    if mode == "manual" and manual_list:
        return manual_list
    auto = track_titles_from_paths(track_paths or [])
    return auto or manual_list


def _layout_columns(layout: str) -> int:
    key = str(layout or "column").lower()
    if key.startswith("grid3"):
        return 3
    if key.startswith("grid2"):
        return 2
    return 1


def _playlist_panel_active(title: dict[str, Any]) -> bool:
    """True when glass plate should rasterize (not just glyph chrome)."""
    opacity = float(title.get("panelOpacity") or 0.0)
    frost = float(title.get("panelFrost") or 0.0)
    border = float(title.get("panelBorderWidth") or 0.0)
    return opacity > 0.02 and (frost > 0.04 or border > 0.05)


def _playlist_panel_padding(title: dict[str, Any], *, font_size: float) -> float:
    frost = float(title.get("panelFrost") or 0.0)
    border = float(title.get("panelBorderWidth") or 0.0)
    return float(max(10.0, font_size * 0.55 + frost * 10.0 + border * 2.0))


TITLE_DOMAIN_DRAG_SOURCES: frozenset[str] = frozenset(
    {
        "titleText",
        "titleTextPanel",
        "titleTextPill",
        "titleTextBadge",
        "titleTextHeader",
        "titleTextHeaderLine",
        "titleTextActivePlate",
        "titleTextStage",
        "titleTextStageOuter",
        "titleTextStagePill",
        "titleTextStageTitle",
        "titleTextStageArtist",
        "titleTextStageArt",
        "titleTextStageBadge",
        "titleTextStageWatermark",
        "titleTextStageBottom",
        "titleTextStageNowPlaying",
        "titleTextStageTransport",
        "titleTextStageTag",
    }
)


def build_playlist_panel_overlay(
    *,
    style: dict[str, Any],
    title: dict[str, Any],
    bounds: dict[str, float],
    header_extra: float = 0.0,
) -> dict[str, Any] | None:
    """Rounded glass plate behind the playlist list (drawn before row glyphs)."""
    if not _playlist_panel_active(title):
        return None
    font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
    pad = _playlist_panel_padding(title, font_size=font_size)
    content_w = float(bounds.get("contentWidth") or 160.0)
    content_h = float(bounds.get("contentHeight") or 40.0) + float(max(0.0, header_extra))
    base_x = float(_style_num(style, "x", 0.0))
    base_y = float(_style_num(style, "y", 0.0)) - float(max(0.0, header_extra))
    frost = float(title.get("panelFrost") or 0.0)
    specular = float(title.get("panelSpecular") or 0.0)
    border_w = float(title.get("panelBorderWidth") or 0.0)
    fill = str(title.get("panelFill") or "#0f172a")
    border_color = str(title.get("panelBorderColor") or "#94a3b8")
    opacity = float(max(0.08, min(0.92, float(title.get("panelOpacity") or 0.45))))
    return {
        "enabled": True,
        "overlayKind": "panel",
        "text": " ",
        "source": "titleTextPanel",
        "anchor": "top-left",
        "x": base_x - pad,
        "y": base_y - pad,
        "panelWidth": content_w + pad * 2.0,
        "panelHeight": content_h + pad * 2.0,
        "panelRadius": float(max(8.0, min(28.0, 12.0 + frost * 8.0))),
        "panelFrost": frost,
        "panelSpecular": specular,
        "color": fill,
        "opacity": opacity,
        "strokeColor": border_color,
        "strokeWidth": border_w,
        "glow": float(min(0.85, specular * 0.55 + frost * 0.2)),
        "glowColor": border_color,
        "shadow": float(min(0.7, 0.2 + frost * 0.45)),
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def build_playlist_tracklist_header_overlay(
    *,
    style: dict[str, Any],
    title: dict[str, Any],
    header_extra: float,
) -> dict[str, Any] | None:
    """TRACKLIST label above the list (Pulse Rail–style)."""
    if not bool(title.get("tracklistHeader")):
        return None
    font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
    base_x = float(_style_num(style, "x", 0.0))
    base_y = float(_style_num(style, "y", 0.0))
    accent = str(title.get("panelBorderColor") or title.get("listColor") or "#e879f9")
    return {
        **_style_to_overlay_fields(style),
        "enabled": True,
        "text": "TRACKLIST",
        "source": "titleTextHeader",
        "anchor": "top-left",
        "x": base_x,
        "y": base_y - float(max(12.0, header_extra * 0.85)),
        "sizePx": float(max(7.0, font_size * 0.72)),
        "fontFamily": "montserrat",
        "bold": True,
        "letterSpacing": 2.2,
        "color": accent,
        "glow": 0.4,
        "glowColor": accent,
        "glowBlur": 8.0,
        "strokeWidth": 0.0,
        "opacity": 0.95,
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def build_playlist_active_row_plate_overlay(
    *,
    style: dict[str, Any],
    title: dict[str, Any],
    active_index: int,
    row_overlays: list[dict[str, Any]],
    bounds: dict[str, float],
) -> dict[str, Any] | None:
    """Magenta neon bar behind the active track row."""
    if not bool(title.get("activeRowPlate")):
        return None
    if active_index < 0 or active_index >= len(row_overlays):
        return None
    active = row_overlays[active_index]
    font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
    line_spacing = float(max(0.8, _style_num(style, "lineSpacing", 1.2)))
    row_h = float(max(font_size * max(1.2, line_spacing), font_size + 6.0))
    pad_x = float(max(6.0, font_size * 0.45))
    pad_y = float(max(2.0, font_size * 0.2))
    width = float(bounds.get("contentWidth") or _style_num(style, "boxWidth", 280.0) or 280.0)
    accent = str(title.get("panelBorderColor") or "#e879f9")
    fill = accent
    ax = float(active.get("x") or _style_num(style, "x", 0.0))
    ay = float(active.get("y") or _style_num(style, "y", 0.0))
    return {
        "enabled": True,
        "overlayKind": "panel",
        "text": " ",
        "source": "titleTextActivePlate",
        "anchor": "top-left",
        "x": ax - pad_x,
        "y": ay - pad_y,
        "panelWidth": width + pad_x * 2.0,
        "panelHeight": row_h + pad_y * 2.0,
        "panelRadius": float(max(6.0, min(16.0, row_h * 0.45))),
        "panelFrost": 0.25,
        "panelSpecular": 0.7,
        "color": fill,
        "opacity": 0.88,
        "strokeColor": accent,
        "strokeWidth": 1.25,
        "glow": 0.55,
        "glowColor": accent,
        "shadow": 0.25,
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def build_playlist_now_playing_pill_overlay(
    *,
    style: dict[str, Any],
    title: dict[str, Any],
    active_index: int,
    row_overlays: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compact NOW PLAYING pill above the active row."""
    if not bool(title.get("nowPlayingPill")):
        return None
    if active_index < 0 or active_index >= len(row_overlays):
        return None
    active = row_overlays[active_index]
    font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
    pill_h = float(max(14.0, font_size * 1.15))
    pill_w = float(max(88.0, font_size * 7.2))
    accent = str(title.get("listActiveColor") or active.get("color") or "#67e8f9")
    border = str(title.get("panelBorderColor") or accent)
    ax = float(active.get("x") or _style_num(style, "x", 0.0))
    ay = float(active.get("y") or _style_num(style, "y", 0.0))
    return {
        "enabled": True,
        "overlayKind": "pill",
        "text": "NOW PLAYING",
        "source": "titleTextPill",
        "anchor": "top-left",
        "x": ax,
        "y": ay - pill_h - max(4.0, font_size * 0.35),
        "panelWidth": pill_w,
        "panelHeight": pill_h,
        "panelRadius": pill_h * 0.5,
        "panelFrost": 0.35,
        "panelSpecular": 0.65,
        "color": accent,
        "opacity": 0.92,
        "strokeColor": border,
        "strokeWidth": 1.0,
        "sizePx": float(max(7.0, font_size * 0.72)),
        "fontFamily": "montserrat",
        "bold": True,
        "animation": "none",
        "startSec": 0.0,
        "durationSec": 1e9,
    }


def playlist_panel_frame_pad(title: dict[str, Any], style: dict[str, Any]) -> float:
    """Extra CapCut frame padding when a glass plate is active."""
    if not _playlist_panel_active(title):
        return 0.0
    font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
    return _playlist_panel_padding(title, font_size=font_size)

def _layout_fill_order(layout: str) -> str:
    """Return ``td`` (column-major / top-down per column) or ``lr`` (row-major)."""
    key = str(layout or "column").lower()
    if key.endswith("_lr"):
        return "lr"
    return "td"


def build_title_overlay_cells(
    titles: list[str],
    *,
    list_style: str,
    layout: str,
    style: dict[str, Any],
    number_indent: str = "aligned",
    list_color: str | None = None,
    list_active_color: str | None = None,
    list_active_index: int = -1,
) -> list[dict[str, Any]]:
    """Build one overlay dict per title cell with layout offsets."""
    cells, _bounds = _build_title_overlay_cells_with_bounds(
        titles,
        list_style=list_style,
        layout=layout,
        style=style,
        number_indent=number_indent,
        list_color=list_color,
        list_active_color=list_active_color,
        list_active_index=list_active_index,
    )
    return cells


def measure_title_layout_bounds(
    titles: list[str],
    *,
    list_style: str,
    layout: str,
    style: dict[str, Any],
    number_indent: str = "aligned",
) -> dict[str, float]:
    """Return content width/height in template units for the title list frame."""
    _cells, bounds = _build_title_overlay_cells_with_bounds(
        titles,
        list_style=list_style,
        layout=layout,
        style=style,
        number_indent=number_indent,
    )
    return bounds


def measure_album_layout_bounds(text: str, style: dict[str, Any]) -> dict[str, float]:
    """Return content width/height in template units for album text."""
    font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
    tracking = float(_style_num(style, "letterSpacing", 0.0))
    line_spacing = float(max(0.8, _style_num(style, "lineSpacing", 1.2)))
    box_w = float(max(0.0, _style_num(style, "boxWidth", 0.0)))
    stroke_w = float(max(0.0, _style_num(style, "strokeWidth", 0.0)))
    family = str(style.get("fontFamily") or "arial")
    bold = bool(style.get("bold", False))
    wrapped = wrap_text_to_box_width(
        text,
        box_width=box_w,
        font_size=font_size,
        letter_spacing=tracking,
        font_family=family,
        bold=bold,
        stroke_width=stroke_w,
    )
    width = measure_text_width_px(
        wrapped,
        font_size=font_size,
        font_family=family,
        bold=bold,
        stroke_width=stroke_w,
        letter_spacing=tracking,
    )
    if box_w > 8.0:
        width = max(width, box_w)
    line_count = max(1, str(wrapped).count("\n") + 1)
    height = max(font_size * max(1.15, line_spacing) * float(line_count), font_size * 1.2)
    return {
        "contentWidth": float(max(40.0, width)),
        "contentHeight": float(max(font_size * 1.2, height)),
        "lineCount": float(line_count),
    }


def _build_title_overlay_cells_with_bounds(
    titles: list[str],
    *,
    list_style: str,
    layout: str,
    style: dict[str, Any],
    number_indent: str = "aligned",
    list_color: str | None = None,
    list_active_color: str | None = None,
    list_active_index: int = -1,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Build title cells and the union bounds of the laid-out list."""
    empty_bounds = {"contentWidth": 160.0, "contentHeight": 40.0, "lineCount": 1.0}
    if not titles:
        return [], empty_bounds
    cols = max(1, _layout_columns(layout))
    order = _layout_fill_order(layout)
    n = len(titles)
    rows = int((n + cols - 1) // cols)
    font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
    line_spacing = float(max(0.8, _style_num(style, "lineSpacing", 1.2)))
    # Row pitch must clear glyph height + stroke/glow padding so list rows
    # share one left indent without overlapping each other.
    stroke_w = float(max(0.0, _style_num(style, "strokeWidth", 0.0)))
    glow_amt = float(max(0.0, _style_num(style, "glow", 0.0)))
    glow_blur = float(max(0.0, _style_num(style, "glowBlur", 8.0))) if glow_amt > 0.01 else 0.0
    shadow_amt = float(max(0.0, _style_num(style, "shadow", 0.0)))
    shadow_blur = float(max(0.0, _style_num(style, "shadowBlur", 0.0))) if shadow_amt > 0.01 else 0.0
    effect_pad = stroke_w * 1.2 + glow_blur * 0.35 + shadow_blur * 0.25
    single_row = max(font_size * max(1.15, line_spacing), font_size + effect_pad + 4.0)
    box_w = float(max(0.0, _style_num(style, "boxWidth", 0.0)))
    tracking = float(_style_num(style, "letterSpacing", 0.0))
    font_family = str(style.get("fontFamily") or "arial")
    bold = bool(style.get("bold", False))
    base = _style_to_overlay_fields(style)
    base_x = float(base.get("x", 0) or 0)
    base_y = float(base.get("y", 0) or 0)
    # Title lists must left-pin each row so numbers share one vertical edge.
    # Center/top anchors center each line on its own width → jagged indent.
    list_anchor = _title_list_anchor(str(base.get("anchor") or "left"))
    # Title lists stay left-pinned so numbers share one edge; Alignment only
    # affects wrapped lines inside each title cell.
    if "right" not in list_anchor:
        list_anchor = "top-left" if "bottom" not in list_anchor else "bottom-left"
    # Force list placement pin regardless of Alignment (drag owns position).
    list_anchor = "top-left"
    style_color = str(base.get("color") or "#ffffff")
    normal_color = normalize_color(list_color, style_color) if list_color else style_color
    active_color = normalize_color(list_active_color, "#fde047") if list_active_color else "#fde047"
    active_idx = int(list_active_index)

    def cell_xy(index: int) -> tuple[int, int]:
        if cols <= 1:
            return 0, index
        if order == "lr":
            return index % cols, index // cols
        # top-down per column
        return index // rows, index % rows

    # Build display strings first, then measure so columns start after the
    # longest title in the previous column (no fixed-gap overlap).
    cells: list[dict[str, Any]] = []
    for index, title in enumerate(titles):
        col, row = cell_xy(index)
        marker = format_title_marker(
            index,
            list_style,
            total=n,
            indent=number_indent,
        )
        text = f"{marker}{title}".strip() if not marker else f"{marker}{title}"
        text = wrap_text_to_box_width(
            text,
            box_width=box_w,
            font_size=font_size,
            letter_spacing=tracking,
            font_family=font_family,
            bold=bold,
            stroke_width=stroke_w,
        )
        width = measure_text_width_px(
            text,
            font_size=font_size,
            font_family=font_family,
            bold=bold,
            stroke_width=stroke_w,
            letter_spacing=tracking,
        )
        if box_w > 8.0:
            width = min(width, box_w)
        cells.append(
            {
                "index": index,
                "col": col,
                "row": row,
                "text": text,
                "width": float(width),
                "line_count": max(1, str(text).count("\n") + 1),
            }
        )

    col_max_w = [0.0] * cols
    for cell in cells:
        col_max_w[int(cell["col"])] = max(col_max_w[int(cell["col"])], float(cell["width"]))
    gutter = max(28.0, font_size * 0.55 + effect_pad)
    col_x = [0.0] * cols
    for c in range(1, cols):
        # Next column starts after previous column's longest title + gutter.
        prev_w = col_max_w[c - 1] if col_max_w[c - 1] > 1.0 else max(font_size * 6.0, 160.0)
        col_x[c] = col_x[c - 1] + prev_w + gutter

    overlays: list[dict[str, Any]] = []
    column_y = [0.0] * max(1, cols)
    for cell in cells:
        col = int(cell["col"])
        row = int(cell["row"])
        cell_h = single_row * float(cell["line_count"])
        if cols <= 1:
            y_off = column_y[0]
            column_y[0] += cell_h
        else:
            # Stack wrapped lines within a column using measured line counts.
            y_off = column_y[col]
            column_y[col] += cell_h
            _ = row
        row_color = active_color if active_idx >= 0 and int(cell["index"]) == active_idx else normal_color
        overlays.append(
            {
                **base,
                "enabled": True,
                "text": cell["text"],
                "color": row_color,
                "anchor": list_anchor,
                "x": base_x + col_x[col],
                "y": base_y + y_off,
                "source": "titleText",
            }
        )

    content_w = col_x[-1] + (col_max_w[-1] if col_max_w[-1] > 1.0 else max(font_size * 6.0, 160.0))
    content_h = max(column_y) if column_y else single_row
    bounds = {
        "contentWidth": float(max(40.0, content_w)),
        "contentHeight": float(max(font_size * 1.2, content_h)),
        "lineCount": float(max(1, n)),
    }
    return overlays, bounds


def _title_list_anchor(anchor: str) -> str:
    """Force horizontal left alignment while keeping vertical placement."""
    a = str(anchor or "left").lower().strip()
    if "right" in a:
        # Explicit right lists stay right-pinned.
        if "top" in a:
            return "top-right"
        if "bottom" in a:
            return "bottom-right"
        return "right"
    if "top" in a:
        return "top-left"
    if "bottom" in a:
        return "bottom-left"
    return "left"


def resolve_title_active_index(
    track_paths: list[str] | None,
    active_track_path: str | None,
    *,
    fallback: int = -1,
) -> int:
    """Map the playing/selected/exporting track to a title-list row index.

    Returns ``fallback`` when the active path is missing or not in the list.
    """
    paths = [str(item or "").strip() for item in (track_paths or []) if str(item or "").strip()]
    active = str(active_track_path or "").strip()
    if not paths or not active:
        return int(fallback)
    active_key = active.replace("\\", "/").lower()
    for index, path in enumerate(paths):
        if path.replace("\\", "/").lower() == active_key:
            return index
    # Basename fallback (pipeline run dirs may differ from workspace paths).
    from pathlib import Path

    active_name = Path(active).name.lower()
    if active_name:
        for index, path in enumerate(paths):
            if Path(path).name.lower() == active_name:
                return index
    return int(fallback)


def expand_text_domains_to_overlays(
    template: dict[str, Any],
    *,
    track_paths: list[str] | None = None,
    pipeline_album: str = "",
    active_track_path: str | None = None,
) -> list[dict[str, Any]]:
    """Build drawable overlays from Album/Title domains only.

    Legacy freeform ``textOverlays`` (old Text tab) are intentionally ignored so
    removed animated text layers cannot reappear in preview/export.

    ``active_track_path`` highlights the matching title row (selected / playing /
    currently exporting track). Falls back to saved ``listActiveIndex``.
    """
    overlays: list[dict[str, Any]] = []

    album = normalize_album_text_settings(template.get("albumText"))
    title = normalize_title_text_settings(template.get("titleText"))
    layout_key = str(title.get("layout") or "").lower()
    list_card_on = bool(title.get("enabled")) and layout_key == "list_card"

    # Album freeform still draws unless list-card owns the artist subtitle.
    if album["enabled"] and not list_card_on:
        text = resolve_album_display_text(album, pipeline_album=pipeline_album)
        if text:
            style = album["style"]
            wrapped = wrap_text_to_box_width(
                text,
                box_width=float(_style_num(style, "boxWidth", 0.0)),
                font_size=float(max(5.0, _style_num(style, "fontSize", 10.0))),
                letter_spacing=float(_style_num(style, "letterSpacing", 0.0)),
                font_family=str(style.get("fontFamily") or "arial"),
                bold=bool(style.get("bold", False)),
                stroke_width=float(max(0.0, _style_num(style, "strokeWidth", 0.0))),
            )
            overlays.append(
                {
                    **_style_to_overlay_fields(style),
                    "enabled": True,
                    "text": wrapped,
                    "source": "albumText",
                }
            )

    if title["enabled"]:
        titles = resolve_title_display_list(title, track_paths=track_paths)
        style = dict(title["style"])
        saved_active = int(title.get("listActiveIndex", -1))
        active_index = resolve_title_active_index(
            track_paths,
            active_track_path,
            fallback=saved_active,
        )
        if not bool(title.get("nowPlayingEnabled", True)):
            active_index = -1

        # Glass Playlist Card — track list in a framed panel only (no full stage).
        if list_card_on and titles:
            from features.video.lib.playlist_list_card import build_playlist_list_card_overlays

            album_name = ""
            if album.get("enabled"):
                album_name = resolve_album_display_text(album, pipeline_album=pipeline_album)
            if not album_name:
                album_name = str(pipeline_album or "").strip()
            overlays.extend(
                build_playlist_list_card_overlays(
                    title=title,
                    titles=titles,
                    active_index=active_index if active_index >= 0 else 0,
                    album_name=album_name,
                    track_paths=track_paths,
                )
            )
            return overlays

        panel_on = _playlist_panel_active(title)
        # When a real glass plate is drawn, keep glyphs clean (no fake stroke chrome).
        if not panel_on:
            border_w = float(title.get("panelBorderWidth") or 0.0)
            specular = float(title.get("panelSpecular") or 0.0)
            frost = float(title.get("panelFrost") or 0.0)
            if border_w > 0.05 or frost > 0.05:
                style["strokeWidth"] = max(float(style.get("strokeWidth") or 0.0), border_w * (0.6 + frost * 0.5))
                style["strokeColor"] = str(title.get("panelBorderColor") or style.get("strokeColor") or "#94a3b8")
                style["glow"] = max(float(style.get("glow") or 0.0), min(0.85, specular * 0.55 + frost * 0.25))
                style["glowColor"] = str(title.get("panelBorderColor") or style.get("glowColor") or "#ffffff")
                style["shadow"] = max(float(style.get("shadow") or 0.0), frost * 0.35)
                style["opacity"] = float(
                    max(
                        0.15,
                        min(
                            1.0,
                            float(style.get("opacity") or 1.0)
                            * (0.75 + float(title.get("panelOpacity") or 0.45) * 0.25),
                        ),
                    )
                )
        display_titles = list(titles)
        # Real pill overlay replaces the old ▶ text prefix.
        row_overlays = build_title_overlay_cells(
            display_titles,
            list_style=str(title["listStyle"]),
            layout=str(title["layout"]),
            style=style,
            number_indent=str(title.get("numberIndent") or "aligned"),
            list_color=str(title.get("listColor") or ""),
            list_active_color=str(title.get("listActiveColor") or ""),
            list_active_index=active_index,
        )
        bounds = measure_title_layout_bounds(
            display_titles,
            list_style=str(title["listStyle"]),
            layout=str(title["layout"]),
            style=style,
            number_indent=str(title.get("numberIndent") or "aligned"),
        )
        font_size = float(max(5.0, _style_num(style, "fontSize", 10.0)))
        header_extra = float(max(16.0, font_size * 1.75)) if bool(title.get("tracklistHeader")) else 0.0
        panel = build_playlist_panel_overlay(
            style=style,
            title=title,
            bounds=bounds,
            header_extra=header_extra,
        )
        if panel is not None:
            overlays.append(panel)
        active_plate = build_playlist_active_row_plate_overlay(
            style=style,
            title=title,
            active_index=active_index,
            row_overlays=row_overlays,
            bounds=bounds,
        )
        if active_plate is not None:
            overlays.append(active_plate)
        header = build_playlist_tracklist_header_overlay(
            style=style,
            title=title,
            header_extra=header_extra,
        )
        if header is not None:
            overlays.append(header)
        overlays.extend(row_overlays)
        pill = build_playlist_now_playing_pill_overlay(
            style=style,
            title=title,
            active_index=active_index,
            row_overlays=row_overlays,
        )
        if pill is not None:
            overlays.append(pill)
        if bool(title.get("trackCountBadge")) and titles:
            badge_style = dict(style)
            badge_style["fontFamily"] = "bebasneue"
            badge_style["fontSize"] = max(28.0, float(style.get("fontSize") or 12.0) * 2.4)
            badge_style["bold"] = False
            badge_style["x"] = float(style.get("x") or 0.0) + float(style.get("boxWidth") or 280.0) * 0.55
            badge_style["y"] = float(style.get("y") or 0.0) + 48.0
            badge_style["align"] = "right"
            badge_style["anchor"] = "top-right"
            badge_style["opacity"] = min(1.0, float(style.get("opacity") or 1.0) * 0.85)
            overlays.append(
                {
                    **_style_to_overlay_fields(badge_style),
                    "enabled": True,
                    "text": str(len(titles)),
                    "source": "titleTextBadge",
                }
            )
    return overlays


def inject_text_domains_into_template(
    template: dict[str, Any],
    *,
    track_paths: list[str] | None = None,
    pipeline_album: str = "",
    active_track_path: str | None = None,
) -> dict[str, Any]:
    """Return a copy of template with textOverlays expanded for GPU draw."""
    out = dict(template)
    out["textOverlays"] = expand_text_domains_to_overlays(
        template,
        track_paths=track_paths,
        pipeline_album=pipeline_album,
        active_track_path=active_track_path,
    )
    return out
