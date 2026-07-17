"""Thumbnail composite pipeline (python_app parity, mode B)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

THUMBNAIL_COMPOSITE_STYLE_INSTRUCTION = (
    "Generate ONLY typography/text on a pure black background. Do not add cars, scenes, "
    "gradients, textures, frames, or extra graphics. "
    "Use the embedded style reference image (in the corner box) only to match typography/text style. "
    "Keep everything except the text pure black. "
    "Text size rules (16:9): the rendered text block (including any glow/outer pixels) should be "
    "about 38–42% of the frame width and 18–22% of the frame height, "
    "centered horizontally and positioned slightly above the vertical middle (center Y ≈ 45% of frame height)."
)

BACKGROUND_NO_TEXT_INSTRUCTION = (
    "Do not generate any text, letters, numbers, typography, logos, watermarks, dates, titles, "
    "labels, stickers, or signage in the background image. No readable characters anywhere."
)

VALID_THUMBNAIL_REFERENCE_MODES = ("composite", "dual_reference")


def normalize_thumbnail_reference_mode(value: str | None) -> str:
    mode = str(value or "composite").strip().lower()
    if mode not in VALID_THUMBNAIL_REFERENCE_MODES:
        return "composite"
    return mode


def resolution_wh(resolution: str) -> tuple[int, int]:
    text = str(resolution or "").strip()
    if "x" not in text:
        return (1920, 1080)
    width_text, height_text = text.split("x", 1)
    try:
        width = max(1, int(width_text))
        height = max(1, int(height_text))
    except ValueError:
        return (1920, 1080)
    return (width, height)


def to_cover_png_bytes(png_bytes: bytes, resolution: str) -> bytes:
    width, height = resolution_wh(resolution)
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    image_width, image_height = image.size
    if image_width <= 0 or image_height <= 0:
        return png_bytes
    scale = max(float(width) / float(image_width), float(height) / float(image_height))
    resized_width = max(1, int(round(float(image_width) * scale)))
    resized_height = max(1, int(round(float(image_height) * scale)))
    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    x = max(0, int((resized_width - width) / 2))
    y = max(0, int((resized_height - height) / 2))
    cropped = resized.crop((x, y, x + width, y + height))
    output = io.BytesIO()
    cropped.save(output, format="PNG")
    return output.getvalue() or png_bytes


def read_cover_image(file_path: str, resolution: str) -> Image.Image:
    path = str(file_path or "").strip()
    image = Image.open(path).convert("RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    cover = Image.open(io.BytesIO(to_cover_png_bytes(buffer.getvalue(), resolution))).convert("RGBA")
    return cover


def build_thumbnail_overlay_input_png(
    overlay_path: str,
    resolution: str,
    style_strength: float,
) -> bytes:
    width, height = resolution_wh(resolution)
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    if not overlay_path or not Path(str(overlay_path)).exists():
        output = io.BytesIO()
        base.save(output, format="PNG")
        return output.getvalue()

    overlay = Image.open(str(overlay_path)).convert("RGBA")
    box_width = max(240, int(round(float(width) * 0.34)))
    box_height = max(200, int(round(float(height) * 0.28)))
    margin = max(16, int(round(float(min(width, height)) * 0.02)))
    padding = max(10, int(round(float(min(width, height)) * 0.012)))
    x0 = max(0, width - box_width - margin)
    y0 = max(0, height - box_height - margin)
    alpha = max(0.0, min(1.0, float(style_strength)))

    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    panel_bg = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 180))
    panel.paste(panel_bg, (x0, y0))

    max_width = max(1, box_width - padding * 2)
    max_height = max(1, box_height - padding * 2)
    overlay_copy = overlay.copy()
    overlay_copy.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    offset_x = x0 + int((box_width - overlay_copy.size[0]) / 2)
    offset_y = y0 + int((box_height - overlay_copy.size[1]) / 2)
    if alpha >= 1.0:
        panel.paste(overlay_copy, (offset_x, offset_y), overlay_copy)
    else:
        alpha_channel = overlay_copy.getchannel("A")
        alpha_channel = alpha_channel.point(lambda value: int(value * alpha))
        overlay_copy.putalpha(alpha_channel)
        panel.paste(overlay_copy, (offset_x, offset_y), overlay_copy)

    composed = Image.alpha_composite(base, panel)
    output = io.BytesIO()
    composed.save(output, format="PNG")
    return output.getvalue()


def chroma_key_black_overlay(png_bytes: bytes, resolution: str) -> Image.Image:
    width, height = resolution_wh(resolution)
    image = Image.open(io.BytesIO(to_cover_png_bytes(png_bytes, resolution))).convert("RGBA")
    pixels = image.load()
    if pixels is None:
        return image
    threshold = 24
    for y_pos in range(height):
        for x_pos in range(width):
            red, green, blue, alpha = pixels[x_pos, y_pos]
            if alpha == 0:
                continue
            if red <= threshold and green <= threshold and blue <= threshold:
                pixels[x_pos, y_pos] = (red, green, blue, 0)
            else:
                pixels[x_pos, y_pos] = (red, green, blue, 255)

    box_width = max(240, int(round(float(width) * 0.34)))
    box_height = max(200, int(round(float(height) * 0.28)))
    margin = max(16, int(round(float(min(width, height)) * 0.02)))
    x0 = max(0, width - box_width - margin)
    y0 = max(0, height - box_height - margin)
    for y_pos in range(y0, min(height, y0 + box_height)):
        for x_pos in range(x0, min(width, x0 + box_width)):
            red, green, blue, _alpha = pixels[x_pos, y_pos]
            pixels[x_pos, y_pos] = (red, green, blue, 0)
    return image


def scale_overlay_center(overlay: Image.Image, scale: float) -> Image.Image:
    factor = float(scale or 1.0)
    if factor >= 0.999:
        return overlay
    width, height = overlay.size
    new_width = max(1, int(round(float(width) * factor)))
    new_height = max(1, int(round(float(height) * factor)))
    resized = overlay.resize((new_width, new_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    offset_x = max(0, int((width - new_width) / 2))
    offset_y = max(0, int((height - new_height) / 2))
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas


def compose_thumbnail_onto_background(
    *,
    background_path: str,
    overlay_png_bytes: bytes,
    resolution: str,
    style_strength: float,
) -> bytes:
    background_cover = read_cover_image(background_path, resolution)
    overlay = chroma_key_black_overlay(overlay_png_bytes, resolution)
    overlay = scale_overlay_center(overlay, 0.91)
    final = Image.alpha_composite(background_cover, overlay)
    output = io.BytesIO()
    final.save(output, format="PNG")
    return output.getvalue()


def enrich_thumbnail_prompt(prompt: str) -> str:
    base = str(prompt or "").strip()
    if THUMBNAIL_COMPOSITE_STYLE_INSTRUCTION in base:
        return base
    if not base:
        return THUMBNAIL_COMPOSITE_STYLE_INSTRUCTION
    return f"{base}\n\n{THUMBNAIL_COMPOSITE_STYLE_INSTRUCTION}".strip()


def enrich_background_prompt(prompt: str) -> str:
    base = str(prompt or "").strip()
    if BACKGROUND_NO_TEXT_INSTRUCTION in base:
        return base
    if not base:
        return BACKGROUND_NO_TEXT_INSTRUCTION
    return f"{base}\n\n{BACKGROUND_NO_TEXT_INSTRUCTION}".strip()
