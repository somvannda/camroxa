"""Draw a text-overlay clip onto the composited RGB frame.

Port of the reference app's `drawText()` / `wrapText()`. Uses Pillow rather
than QPainter so this module works identically whether called from the live
preview (Qt event loop) or the offline export pipeline (background thread /
subprocess-adjacent code, no GUI context required).
"""

from __future__ import annotations

import functools
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from studio.core.models import Clip

_LINE_SPACING = 1.25
_SHADOW_OFFSET = 2
_SHADOW_ALPHA = 140

_FONT_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf"),
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "arialbd.ttf",
    "arial.ttf",
    "DejaVuSans-Bold.ttf",
]


@functools.lru_cache(maxsize=32)
def _get_font(size_px: int) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size_px)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = (hex_color or "#ffffff").lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (255, 255, 255)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if width <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines or [""]


def draw_text_overlay(canvas: np.ndarray, clip: Clip, opacity: float) -> None:
    """Composite `clip.text` onto `canvas` (HxWx3 uint8 RGB) in place."""
    if not clip.text or opacity <= 0.0:
        return
    h, w = canvas.shape[:2]
    if h <= 0 or w <= 0:
        return

    size_px = max(8, int(clip.size or 32))
    color = _hex_to_rgb(clip.color or "#ffffff")
    cx = (clip.x if clip.x is not None else 0.5) * w
    cy = (clip.y if clip.y is not None else 0.5) * h

    font = _get_font(size_px)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    lines = _wrap_text(draw, clip.text, font, max_width=w * 0.86)
    line_height = size_px * _LINE_SPACING
    total_height = line_height * len(lines)
    y = cy - total_height / 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = cx - line_w / 2
        draw.text((x + _SHADOW_OFFSET, y + _SHADOW_OFFSET), line, font=font, fill=(0, 0, 0, _SHADOW_ALPHA))
        draw.text((x, y), line, font=font, fill=(*color, 255))
        y += line_height

    layer_arr = np.asarray(layer, dtype=np.float32)
    alpha = (layer_arr[..., 3] / 255.0) * opacity
    if not np.any(alpha):
        return
    rgb = layer_arr[..., :3]
    alpha3 = alpha[..., None]
    canvas_f = canvas.astype(np.float32)
    blended = canvas_f * (1 - alpha3) + rgb * alpha3
    canvas[:] = np.clip(blended, 0, 255).astype(np.uint8)
