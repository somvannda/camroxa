from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFilter, ImageFont

if TYPE_CHECKING:
    from .font_manager import FontManager

logger = logging.getLogger(__name__)

_RGBA_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{8}$")

_MIN_FONT_SIZE = 12

_VALID_POSITIONS = ("top", "center", "bottom")
_VALID_ALIGNMENTS = ("left", "center", "right")


@dataclass
class TextStylePreset:
    """Immutable style configuration for text rendering."""

    name: str
    font_path: str
    font_size: int  # pixels, 12–400
    primary_color: str  # RGBA hex e.g. "#FF0000FF"
    position: str  # "top" | "center" | "bottom"

    # Effects (optional with defaults)
    glow_color: str = "#00000000"
    glow_radius: int = 0  # 0–50
    shadow_offset_x: int = 0
    shadow_offset_y: int = 0
    shadow_color: str = "#00000080"
    stroke_width: int = 0  # 0–10
    stroke_color: str = "#000000FF"

    # Gradient
    gradient_enabled: bool = False
    gradient_start_color: str = "#FFFFFFFF"
    gradient_end_color: str = "#000000FF"

    # Layout
    line_spacing: float = 1.4  # 1.0–3.0
    alignment: str = "center"  # "left" | "center" | "right"
    max_text_width_pct: int = 80  # 20–90
    vertical_padding_pct: int = 10  # 2–30


def validate_preset(preset: TextStylePreset) -> list[str]:
    """
    Validate preset field constraints. Returns list of error messages (empty = valid).

    Checks: font_size 12–400, glow_radius 0–50, stroke_width 0–10,
    line_spacing 1.0–3.0, max_text_width_pct 20–90, vertical_padding_pct 2–30,
    colors are valid RGBA hex, position/alignment are valid enum values.
    """
    errors: list[str] = []

    # Name must be non-empty
    if not preset.name or not preset.name.strip():
        errors.append("name must be non-empty")

    # Numeric range checks
    if not (12 <= preset.font_size <= 400):
        errors.append(f"font_size must be between 12 and 400, got {preset.font_size}")

    if not (0 <= preset.glow_radius <= 50):
        errors.append(f"glow_radius must be between 0 and 50, got {preset.glow_radius}")

    if not (0 <= preset.stroke_width <= 10):
        errors.append(f"stroke_width must be between 0 and 10, got {preset.stroke_width}")

    if not (1.0 <= preset.line_spacing <= 3.0):
        errors.append(f"line_spacing must be between 1.0 and 3.0, got {preset.line_spacing}")

    if not (20 <= preset.max_text_width_pct <= 90):
        errors.append(
            f"max_text_width_pct must be between 20 and 90, got {preset.max_text_width_pct}"
        )

    if not (2 <= preset.vertical_padding_pct <= 30):
        errors.append(
            f"vertical_padding_pct must be between 2 and 30, got {preset.vertical_padding_pct}"
        )

    # Enum checks
    if preset.position not in _VALID_POSITIONS:
        errors.append(
            f"position must be one of {_VALID_POSITIONS}, got '{preset.position}'"
        )

    if preset.alignment not in _VALID_ALIGNMENTS:
        errors.append(
            f"alignment must be one of {_VALID_ALIGNMENTS}, got '{preset.alignment}'"
        )

    # RGBA hex color checks
    color_fields = [
        ("primary_color", preset.primary_color),
        ("glow_color", preset.glow_color),
        ("shadow_color", preset.shadow_color),
        ("stroke_color", preset.stroke_color),
        ("gradient_start_color", preset.gradient_start_color),
        ("gradient_end_color", preset.gradient_end_color),
    ]
    for field_name, value in color_fields:
        if not _RGBA_HEX_RE.match(value):
            errors.append(
                f"{field_name} must be a valid RGBA hex string (e.g. '#FF0000FF'), got '{value}'"
            )

    return errors


def _parse_rgba_hex(color: str) -> tuple[int, int, int, int]:
    """Parse '#RRGGBBAA' hex string to (R, G, B, A) tuple."""
    color = color.lstrip("#")
    return (
        int(color[0:2], 16),
        int(color[2:4], 16),
        int(color[4:6], 16),
        int(color[6:8], 16),
    )


def _measure_text_lines(
    draw: ImageDraw.ImageDraw,
    titles: list[str],
    font: ImageFont.FreeTypeFont,
) -> list[tuple[int, int]]:
    """Measure width and height of each title line. Returns list of (width, height)."""
    measurements: list[tuple[int, int]] = []
    for title in titles:
        bbox = draw.textbbox((0, 0), title, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        measurements.append((w, h))
    return measurements


def _find_fitting_font_size(
    draw: ImageDraw.ImageDraw,
    titles: list[str],
    preset: TextStylePreset,
    max_width_px: int,
    font_manager: "FontManager | None",
) -> tuple[ImageFont.FreeTypeFont, int]:
    """
    Find the largest font size (starting from preset.font_size) where all lines
    fit within max_width_px. Reduces by 2px per iteration down to _MIN_FONT_SIZE.
    Returns (font, actual_font_size).
    """
    size = preset.font_size

    while size >= _MIN_FONT_SIZE:
        font = _load_font(preset.font_path, size, font_manager)
        measurements = _measure_text_lines(draw, titles, font)
        max_line_width = max(w for w, _ in measurements) if measurements else 0

        if max_line_width <= max_width_px:
            return font, size

        # Reduce font size
        size -= 2
        if size < _MIN_FONT_SIZE:
            size = _MIN_FONT_SIZE
            break

    # Use minimum font size — text may still overflow, but we don't go smaller
    font = _load_font(preset.font_path, size, font_manager)
    if size < _MIN_FONT_SIZE:
        font = _load_font(preset.font_path, _MIN_FONT_SIZE, font_manager)
    return font, max(size, _MIN_FONT_SIZE)


def _load_font(
    font_path: str, size: int, font_manager: "FontManager | None"
) -> ImageFont.FreeTypeFont:
    """Load a font using the FontManager if available, else fall back to Pillow default."""
    if font_manager is not None:
        return font_manager.load_font(font_path, size)
    # Fallback: use Pillow's built-in default font
    return ImageFont.load_default(size)


def _calculate_text_block_y(
    position: str,
    canvas_height: int,
    text_block_height: int,
    vertical_padding_pct: int,
) -> int:
    """Calculate the top Y coordinate for the text block based on position setting."""
    padding_px = int(canvas_height * vertical_padding_pct / 100)

    if position == "top":
        return padding_px
    elif position == "bottom":
        return canvas_height - text_block_height - padding_px
    else:  # "center"
        return (canvas_height - text_block_height) // 2


def _calculate_line_x(
    alignment: str,
    line_width: int,
    canvas_width: int,
    max_width_px: int,
) -> int:
    """Calculate X coordinate for a line based on alignment."""
    # The text region is centered on the canvas
    region_left = (canvas_width - max_width_px) // 2

    if alignment == "left":
        return region_left
    elif alignment == "right":
        return region_left + max_width_px - line_width
    else:  # "center"
        return (canvas_width - line_width) // 2


def _render_shadow_layer(
    titles: list[str],
    preset: TextStylePreset,
    font: ImageFont.FreeTypeFont,
    measurements: list[tuple[int, int]],
    line_step: int,
    block_y: int,
    width: int,
    height: int,
    max_width_px: int,
) -> Image.Image:
    """Render shadow layer: text at shadow offset in shadow_color."""
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    shadow_color = _parse_rgba_hex(preset.shadow_color)

    for i, title in enumerate(titles):
        line_width, _ = measurements[i]
        y = block_y + (i * line_step) + preset.shadow_offset_y
        x = _calculate_line_x(preset.alignment, line_width, width, max_width_px) + preset.shadow_offset_x
        draw.text((x, y), title, font=font, fill=shadow_color)

    return layer


def _render_glow_layer(
    titles: list[str],
    preset: TextStylePreset,
    font: ImageFont.FreeTypeFont,
    measurements: list[tuple[int, int]],
    line_step: int,
    block_y: int,
    width: int,
    height: int,
    max_width_px: int,
) -> Image.Image:
    """Render glow layer: text in glow_color with Gaussian blur applied."""
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    glow_color = _parse_rgba_hex(preset.glow_color)

    for i, title in enumerate(titles):
        line_width, _ = measurements[i]
        y = block_y + (i * line_step)
        x = _calculate_line_x(preset.alignment, line_width, width, max_width_px)
        draw.text((x, y), title, font=font, fill=glow_color)

    # Apply Gaussian blur to the entire glow layer
    layer = layer.filter(ImageFilter.GaussianBlur(radius=preset.glow_radius))
    return layer


def _render_stroke_layer(
    titles: list[str],
    preset: TextStylePreset,
    font: ImageFont.FreeTypeFont,
    measurements: list[tuple[int, int]],
    line_step: int,
    block_y: int,
    width: int,
    height: int,
    max_width_px: int,
) -> Image.Image:
    """Render stroke layer: text outline at stroke_width and stroke_color."""
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    stroke_color = _parse_rgba_hex(preset.stroke_color)

    for i, title in enumerate(titles):
        line_width, _ = measurements[i]
        y = block_y + (i * line_step)
        x = _calculate_line_x(preset.alignment, line_width, width, max_width_px)
        # Draw text with stroke only (transparent fill so only outline shows)
        draw.text(
            (x, y),
            title,
            font=font,
            fill=(0, 0, 0, 0),
            stroke_width=preset.stroke_width,
            stroke_fill=stroke_color,
        )

    return layer


def _render_fill_layer(
    titles: list[str],
    preset: TextStylePreset,
    font: ImageFont.FreeTypeFont,
    measurements: list[tuple[int, int]],
    line_step: int,
    block_y: int,
    width: int,
    height: int,
    max_width_px: int,
) -> Image.Image:
    """Render fill layer: text in primary_color or gradient if enabled."""
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    if preset.gradient_enabled:
        # Gradient fill: draw text in white, create gradient, use text as mask
        text_mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(text_mask)

        for i, title in enumerate(titles):
            line_width, _ = measurements[i]
            y = block_y + (i * line_step)
            x = _calculate_line_x(preset.alignment, line_width, width, max_width_px)
            mask_draw.text((x, y), title, font=font, fill=255)

        # Create vertical linear gradient from start_color to end_color
        gradient = _create_vertical_gradient(
            width, height,
            _parse_rgba_hex(preset.gradient_start_color),
            _parse_rgba_hex(preset.gradient_end_color),
        )

        # Apply text mask to gradient
        gradient.putalpha(text_mask)
        layer = gradient
    else:
        # Solid fill with primary_color
        draw = ImageDraw.Draw(layer)
        fill_color = _parse_rgba_hex(preset.primary_color)

        for i, title in enumerate(titles):
            line_width, _ = measurements[i]
            y = block_y + (i * line_step)
            x = _calculate_line_x(preset.alignment, line_width, width, max_width_px)
            draw.text((x, y), title, font=font, fill=fill_color)

    return layer


def _create_vertical_gradient(
    width: int,
    height: int,
    start_color: tuple[int, int, int, int],
    end_color: tuple[int, int, int, int],
) -> Image.Image:
    """Create a vertical linear gradient image from start_color (top) to end_color (bottom)."""
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    if height <= 1:
        # Degenerate case — use start_color
        gradient = Image.new("RGBA", (width, height), start_color)
        return gradient

    draw = ImageDraw.Draw(gradient)
    for y in range(height):
        # Linear interpolation factor
        t = y / (height - 1)
        r = int(start_color[0] + (end_color[0] - start_color[0]) * t)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * t)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * t)
        a = int(start_color[3] + (end_color[3] - start_color[3]) * t)
        # Draw a horizontal line at this y position
        draw.line([(0, y), (width - 1, y)], fill=(r, g, b, a))

    return gradient


def render_text_overlay(
    titles: list[str],
    preset: TextStylePreset,
    width: int,
    height: int,
    font_manager: "FontManager | None" = None,
) -> Image.Image:
    """
    Render track titles as a styled transparent RGBA overlay.

    Returns an RGBA Image at (width, height) with only the text rendered.
    If titles is empty, returns a fully transparent image.

    Effect layer ordering (back to front): shadow → glow → stroke → fill.
    """
    # Create transparent RGBA canvas
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    if not titles:
        return canvas

    draw = ImageDraw.Draw(canvas)

    # Calculate max width in pixels from percentage
    max_width_px = int(width * preset.max_text_width_pct / 100)

    # Find font size that fits all lines within max width
    font, actual_size = _find_fitting_font_size(
        draw, titles, preset, max_width_px, font_manager
    )

    # Measure final line dimensions
    measurements = _measure_text_lines(draw, titles, font)

    # Calculate line spacing in pixels (baseline to baseline)
    line_step = int(actual_size * preset.line_spacing)

    # Calculate total text block height
    if len(titles) == 1:
        text_block_height = measurements[0][1]
    else:
        text_block_height = line_step * (len(titles) - 1) + measurements[-1][1]

    # Calculate vertical starting position for the text block
    block_y = _calculate_text_block_y(
        preset.position, height, text_block_height, preset.vertical_padding_pct
    )

    # Common args for layer rendering helpers
    layer_args = (
        titles, preset, font, measurements, line_step,
        block_y, width, height, max_width_px,
    )

    # Layer compositing: shadow → glow → stroke → fill (back to front)

    # 1. Shadow layer (only if shadow offset is non-zero)
    if preset.shadow_offset_x != 0 or preset.shadow_offset_y != 0:
        shadow_layer = _render_shadow_layer(*layer_args)
        canvas = Image.alpha_composite(canvas, shadow_layer)

    # 2. Glow layer (only if glow_radius > 0)
    if preset.glow_radius > 0:
        glow_layer = _render_glow_layer(*layer_args)
        canvas = Image.alpha_composite(canvas, glow_layer)

    # 3. Stroke layer (only if stroke_width > 0)
    if preset.stroke_width > 0:
        stroke_layer = _render_stroke_layer(*layer_args)
        canvas = Image.alpha_composite(canvas, stroke_layer)

    # 4. Fill layer (solid primary_color or gradient)
    fill_layer = _render_fill_layer(*layer_args)
    canvas = Image.alpha_composite(canvas, fill_layer)

    return canvas
