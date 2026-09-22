"""Music visualizer draw routines — Bars, Mirror Bars, Waveform, Radial.

Port of the reference app's `drawVisualizer()`. `bars`/`mirror-bars`/`circle`
are driven by the precomputed STFT band grid (`AudioSource.get_spectrum_bands`);
`wave` is driven by the raw time-domain samples (`AudioSource.get_waveform_samples`).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

_BAR_ALPHA = 205
_WAVE_ALPHA = 220
_RADIAL_ALPHA = 210


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = (hex_color or "#ffffff").lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (255, 255, 255)


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))  # type: ignore[return-value]


def _draw_bars(draw: ImageDraw.ImageDraw, values: np.ndarray, w: int, h: int, c1, c2, mirror: bool) -> None:
    n = max(1, len(values))
    bar_w = w / n
    baseline = h * 0.5 if mirror else h - 12
    max_extent = h * 0.42 if mirror else h * 0.62
    for i, v in enumerate(values):
        t = i / max(1, n - 1)
        color = _lerp_color(c1, c2, t)
        bar_h = max(2.0, float(v) * max_extent)
        x0, x1 = i * bar_w + 1, (i + 1) * bar_w - 1
        if mirror:
            draw.rectangle([x0, baseline - bar_h, x1, baseline + bar_h], fill=(*color, _BAR_ALPHA))
        else:
            draw.rectangle([x0, baseline - bar_h, x1, baseline], fill=(*color, _BAR_ALPHA))


def _draw_wave(draw: ImageDraw.ImageDraw, samples: np.ndarray, w: int, h: int, c1, c2) -> None:
    n = len(samples)
    if n < 2:
        return
    mid = h * 0.5
    points = []
    for i, s in enumerate(samples):
        x = i / (n - 1) * w
        y = mid - float(s) * h * 0.38
        points.append((x, y))
    draw.line(points, fill=(*c1, _WAVE_ALPHA), width=max(2, w // 400))


def _draw_radial(draw: ImageDraw.ImageDraw, values: np.ndarray, w: int, h: int, c1, c2) -> None:
    n = max(1, len(values))
    cx, cy = w / 2, h / 2
    base_r = min(w, h) * 0.16
    max_extra = min(w, h) * 0.20
    line_width = max(2, int(min(w, h) / 220))
    for i, v in enumerate(values):
        angle = (2 * math.pi * i / n) - (math.pi / 2)
        t = i / max(1, n - 1)
        color = _lerp_color(c1, c2, t)
        r0 = base_r
        r1 = base_r + max_extra * float(v)
        x0, y0 = cx + r0 * math.cos(angle), cy + r0 * math.sin(angle)
        x1, y1 = cx + r1 * math.cos(angle), cy + r1 * math.sin(angle)
        draw.line([(x0, y0), (x1, y1)], fill=(*color, _RADIAL_ALPHA), width=line_width)


def draw_visualizer(
    canvas: np.ndarray,
    style: str,
    band_values: np.ndarray,
    wave_values: np.ndarray,
    color_from: str,
    color_to: str,
    opacity: float = 1.0,
) -> None:
    """Composite a visualizer overlay onto `canvas` (HxWx3 uint8 RGB) in place."""
    if opacity <= 0.0:
        return
    h, w = canvas.shape[:2]
    if h <= 0 or w <= 0:
        return

    c1, c2 = _hex_to_rgb(color_from), _hex_to_rgb(color_to)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if style == "bars":
        _draw_bars(draw, band_values, w, h, c1, c2, mirror=False)
    elif style == "mirror-bars":
        _draw_bars(draw, band_values, w, h, c1, c2, mirror=True)
    elif style == "wave":
        _draw_wave(draw, wave_values, w, h, c1, c2)
    elif style == "circle":
        _draw_radial(draw, band_values, w, h, c1, c2)
    else:
        return

    layer_arr = np.asarray(layer, dtype=np.float32)
    alpha = (layer_arr[..., 3] / 255.0) * opacity
    if not np.any(alpha):
        return
    rgb = layer_arr[..., :3]
    alpha3 = alpha[..., None]
    canvas_f = canvas.astype(np.float32)
    blended = canvas_f * (1 - alpha3) + rgb * alpha3
    canvas[:] = np.clip(blended, 0, 255).astype(np.uint8)
