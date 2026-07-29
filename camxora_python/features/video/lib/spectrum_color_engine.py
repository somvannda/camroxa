"""Spectrum layer color engine — port of spectrumColorEngine.ts."""

from __future__ import annotations

from typing import Any

import numpy as np

from features.video.lib.template_value_utils import normalize_color, to_record, to_string_value

MAX_GRADIENT_COLOR_STOPS = 5
GRADIENT_FALLBACK_COLOR = "#22d3ee"

VALID_GRADIENT_DIRECTIONS = frozenset(
    {"left-to-right", "top-to-bottom", "diagonal", "radial", "circular"}
)

SPECTRUM_GRADIENT_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("#ff00ff,#00ffff", "Cyber Blue"),
    ("#ff8800,#ff0000", "EDM Fire"),
    ("#00ff00,#ffff00", "Toxic"),
    ("#8a2be2,#4b0082", "Galaxy"),
    ("#22d3ee,#67e8f9,#a5f3fc", "Ice"),
    ("#ff4500,#ff1493", "Lava"),
    ("#ff8c00,#ff69b4", "Sunset"),
    ("#ff0000,#00ff00,#0000ff", "RGB Flow"),
    ("#ec4899,#8b5cf6,#22d3ee", "Aurora"),
    ("#fde68a,#fb7185,#c084fc,#60a5fa", "Festival"),
    ("#22c55e,#14b8a6,#06b6d4,#3b82f6", "Emerald Wave"),
    ("#f472b6,#fde68a,#f97316,#ef4444", "Solar Bloom"),
)


def get_spectrum_layer_color_fallback(index: int) -> str:
    return "#8b5cf6" if index % 2 == 0 else "#22d3ee"


def _normalize_spectrum_color(value: Any, fallback: str) -> str:
    raw = to_string_value(value, "")
    if not raw:
        return fallback
    return normalize_color(raw, fallback)


def _extract_color_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    record = to_record(value)
    for key in ("color", "value", "hex", "solidColor"):
        text = to_string_value(record.get(key), "")
        if text:
            return text
    return ""


def normalize_spectrum_gradient_colors(raw_colors: list[Any], fallback: str) -> list[str]:
    normalized = [
        color
        for color in (
            _normalize_spectrum_color(_extract_color_value(value), "")
            for value in raw_colors
        )
        if color
    ][:MAX_GRADIENT_COLOR_STOPS]

    if len(normalized) >= 2:
        return normalized
    if len(normalized) == 1:
        return [normalized[0], GRADIENT_FALLBACK_COLOR]
    return [fallback, GRADIENT_FALLBACK_COLOR]


def extract_spectrum_layer_color_model(
    layer_record: dict[str, Any] | None,
    fallback: str,
) -> dict[str, Any]:
    record = layer_record or {}
    nested = to_record(record.get("color"))
    raw_color = nested if nested else {
        "mode": record.get("colorMode"),
        "solidColor": record.get("solidColor"),
        "gradientDirection": record.get("gradientDirection"),
        "gradientColors": record.get("gradientColors"),
    }

    mode = "gradient" if to_string_value(raw_color.get("mode"), "solid").lower() == "gradient" else "solid"
    solid_color = _normalize_spectrum_color(
        raw_color.get("solidColor") or raw_color.get("color") or raw_color.get("value"),
        fallback,
    )
    direction = to_string_value(raw_color.get("gradientDirection"), "left-to-right").lower()
    if direction not in VALID_GRADIENT_DIRECTIONS:
        direction = "left-to-right"
    gradient_colors = normalize_spectrum_gradient_colors(
        list(raw_color.get("gradientColors") or []) if isinstance(raw_color.get("gradientColors"), list) else [],
        solid_color,
    )

    return {
        "mode": mode,
        "solidColor": solid_color,
        "gradientDirection": direction,
        "gradientColors": gradient_colors,
        "colors": gradient_colors if mode == "gradient" else [solid_color],
    }


def build_spectrum_gradient_preset_value(colors: list[str]) -> str:
    return ",".join(colors)


def _hex_to_rgb01(value: str) -> np.ndarray:
    raw = str(value or "").strip()
    if raw.startswith("#") and len(raw) >= 7:
        try:
            return np.array(
                (
                    int(raw[1:3], 16),
                    int(raw[3:5], 16),
                    int(raw[5:7], 16),
                ),
                dtype=np.float32,
            ) / 255.0
        except ValueError:
            pass
    return np.array((1.0, 1.0, 1.0), dtype=np.float32)


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.power(np.clip(rgb, 0.0, 1.0), 2.2).astype(np.float32)


def _linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    return np.power(np.clip(rgb, 0.0, 1.0), 1.0 / 2.2).astype(np.float32)


def build_spectrum_vertex_rgba(
    *,
    mode: str,
    solid_color: str,
    gradient_colors: list[str] | None,
    count: int,
    alpha: float,
) -> np.ndarray:
    """Build per-bar RGBA colors for preview/export spectrum draws.

    Multi-stop gradients interpolate through every stop (not first→last only).
    """
    n = int(max(1, count))
    a = float(max(0.0, min(1.0, alpha)))
    if str(mode or "solid").lower().strip() == "gradient":
        stops_raw = [str(c).strip() for c in (gradient_colors or []) if str(c or "").strip()]
        stops_raw = normalize_spectrum_gradient_colors(stops_raw, solid_color or GRADIENT_FALLBACK_COLOR)
        stops = np.stack([_hex_to_rgb01(c) for c in stops_raw], axis=0).astype(np.float32)
        stops_lin = _srgb_to_linear(stops)
        if stops.shape[0] >= 2:
            t = np.linspace(0.0, 1.0, n, dtype=np.float32)
            segment_count = int(stops.shape[0] - 1)
            scaled = t * float(segment_count)
            seg_idx = np.minimum(segment_count - 1, np.floor(scaled).astype(np.int32))
            local_t = (scaled - seg_idx.astype(np.float32)).reshape((n, 1))
            c1 = stops_lin[seg_idx]
            c2 = stops_lin[np.minimum(seg_idx + 1, stops_lin.shape[0] - 1)]
            rgb_lin = c1 * (1.0 - local_t) + c2 * local_t
            rgb = _linear_to_srgb(rgb_lin)
            alpha_col = np.full((n, 1), a, dtype=np.float32)
            return np.concatenate([rgb.astype(np.float32), alpha_col], axis=1)

    base = _hex_to_rgb01(solid_color)
    return np.tile(np.array([base[0], base[1], base[2], a], dtype=np.float32)[None, :], (n, 1))


def build_spectrum_bar_quad_rgba(
    *,
    mode: str,
    solid_color: str,
    gradient_colors: list[str] | None,
    count: int,
    alpha: float,
    gradient_direction: str,
) -> np.ndarray:
    """Build per-vertex RGBA rows for TRIANGLES bar quads.

    Default behavior follows ring/index interpolation. For ``top-to-bottom`` /
    ``radial``, bars use base->tip vertical gradient from first->last stop.
    ``diagonal`` blends around-ring color with tip color on tip vertices.
    ``circular`` follows around-ring stops (same as left-to-right).
    """
    n = int(max(1, count))
    direction = str(gradient_direction or "left-to-right").lower().strip()
    if direction == "radial":
        direction = "top-to-bottom"
    if direction == "circular":
        direction = "left-to-right"
    per_bar = build_spectrum_vertex_rgba(
        mode=mode,
        solid_color=solid_color,
        gradient_colors=gradient_colors,
        count=n,
        alpha=alpha,
    )
    if str(mode or "solid").lower().strip() != "gradient":
        return np.repeat(per_bar, 6, axis=0).astype(np.float32)
    if direction == "left-to-right":
        return np.repeat(per_bar, 6, axis=0).astype(np.float32)

    stops_raw = [str(c).strip() for c in (gradient_colors or []) if str(c or "").strip()]
    stops_raw = normalize_spectrum_gradient_colors(stops_raw, solid_color or GRADIENT_FALLBACK_COLOR)
    base_rgb = _hex_to_rgb01(stops_raw[0])
    tip_rgb = _hex_to_rgb01(stops_raw[-1])
    a = float(max(0.0, min(1.0, alpha)))
    base = np.array([base_rgb[0], base_rgb[1], base_rgb[2], a], dtype=np.float32)
    tip = np.array([tip_rgb[0], tip_rgb[1], tip_rgb[2], a], dtype=np.float32)
    rows = np.empty((n * 6, 4), dtype=np.float32)
    # TRIANGLES order from _spectrum_fast._pack:
    # 0 p0(base), 1 p1(base), 2 p2(tip), 3 p0(base), 4 p2(tip), 5 p3(tip)
    if direction == "top-to-bottom":
        rows[0::6] = base
        rows[1::6] = base
        rows[2::6] = tip
        rows[3::6] = base
        rows[4::6] = tip
        rows[5::6] = tip
        return rows

    # diagonal: keep around-ring hue on base, blend toward tip color on tips
    tip_mix = (per_bar * 0.45 + tip.reshape(1, 4) * 0.55).astype(np.float32)
    rows[0::6] = per_bar
    rows[1::6] = per_bar
    rows[2::6] = tip_mix
    rows[3::6] = per_bar
    rows[4::6] = tip_mix
    rows[5::6] = tip_mix
    return rows


def dampen_spectrum_glow_rgba(colors: np.ndarray, *, strength: float = 0.42) -> np.ndarray:
    """Keep glow passes colorful instead of washing toward white haze."""
    out = np.asarray(colors, dtype=np.float32).copy()
    if out.ndim != 2 or out.shape[1] < 3:
        return out
    s = float(max(0.15, min(1.0, strength)))
    out[:, 0:3] *= s
    if out.shape[1] >= 4:
        out[:, 3] = np.clip(out[:, 3] * min(1.0, s + 0.25), 0.0, 1.0)
    return out


def apply_spectrum_layer_color_patch(
    layer_record: dict[str, Any],
    patch: dict[str, Any],
    fallback: str,
) -> dict[str, Any]:
    current = extract_spectrum_layer_color_model(layer_record, fallback)
    next_mode = (
        current["mode"]
        if patch.get("mode") is None
        else ("gradient" if to_string_value(patch.get("mode"), "solid").lower() == "gradient" else "solid")
    )
    next_solid = (
        current["solidColor"]
        if patch.get("solidColor") is None
        else _normalize_spectrum_color(patch.get("solidColor"), current["solidColor"])
    )
    next_direction = (
        current["gradientDirection"]
        if patch.get("gradientDirection") is None
        else to_string_value(patch.get("gradientDirection"), current["gradientDirection"]).lower()
    )
    if next_direction not in VALID_GRADIENT_DIRECTIONS:
        next_direction = current["gradientDirection"]
    next_gradient = (
        current["gradientColors"]
        if patch.get("gradientColors") is None
        else normalize_spectrum_gradient_colors(list(patch.get("gradientColors") or []), next_solid)
    )
    nested = to_record(layer_record.get("color"))

    return {
        **layer_record,
        "colorMode": next_mode,
        "solidColor": next_solid,
        "gradientColors": next_gradient,
        "gradientDirection": next_direction,
        "color": {
            **nested,
            "mode": next_mode,
            "solidColor": next_solid,
            "gradientColors": next_gradient,
            "gradientDirection": next_direction,
        },
    }
