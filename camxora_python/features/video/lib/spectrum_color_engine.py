"""Spectrum layer color engine — port of spectrumColorEngine.ts."""

from __future__ import annotations

from typing import Any

import numpy as np

from features.video.lib.template_value_utils import normalize_color, to_record, to_string_value

MAX_GRADIENT_COLOR_STOPS = 12
GRADIENT_FALLBACK_COLOR = "#22d3ee"

VALID_GRADIENT_DIRECTIONS = frozenset(
    {"left-to-right", "top-to-bottom", "diagonal", "radial", "circular"}
)

# Bright / light spectrum gradient catalogs (UI dropdown + style recipes).
# Avoid pure white lead stops — they wash bars to chalk on dark stage.
SPECTRUM_GRADIENT_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("#ff4fd8,#22d3ee,#a78bfa,#f472b6", "Neon Candy"),
    ("#38bdf8,#22d3ee,#818cf8,#c084fc", "Electric Sky"),
    ("#fb7185,#f472b6,#e879f9,#c084fc", "Hot Magenta"),
    ("#fb923c,#fbbf24,#f472b6,#a78bfa", "Solar Pop"),
    ("#2dd4bf,#22d3ee,#60a5fa,#a78bfa", "Mint Freeze"),
    ("#ff00ff,#00ffff,#a78bfa,#f472b6", "Prism Beam"),
    ("#a3e635,#22d3ee,#818cf8,#f472b6", "Lime Pulse"),
    ("#fb7185,#fb923c,#fbbf24,#38bdf8", "Coral Wave"),
    ("#c084fc,#a78bfa,#67e8f9,#22d3ee", "Violet Ice"),
    ("#fda4af,#fb7185,#f0abfc,#7dd3fc", "Peach Neon"),
    ("#67e8f9,#22d3ee,#fb923c,#f472b6", "Aqua Flame"),
    ("#f472b6,#a78bfa,#38bdf8,#34d399", "Prism Bright"),
)


def spectrum_gradient_preset_colors(preset_value: str) -> list[str]:
    """Split a comma-joined palette preset into hex stops."""
    return [part.strip() for part in str(preset_value or "").split(",") if part.strip()]


def get_spectrum_layer_color_fallback(index: int) -> str:
    return "#ff4fd8" if index % 2 == 0 else "#22d3ee"


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


def _smoothstep01(t: np.ndarray) -> np.ndarray:
    """Hermite smoothstep so stop transitions blend instead of hard linear cuts."""
    x = np.clip(t, 0.0, 1.0)
    return (x * x * (3.0 - 2.0 * x)).astype(np.float32)


def _mix_neighbor_rgb(rgb: np.ndarray, *, strength: float = 0.35) -> np.ndarray:
    """Soft-mix adjacent bar colors so around-ring hues join as a continuous wash.

    Edges are clamped (no wrap) so linear left→right gradients keep true end stops.
    """
    n = int(rgb.shape[0])
    if n < 3 or strength <= 0.0:
        return rgb
    s = float(max(0.0, min(0.5, strength)))
    prev_idx = np.concatenate(([0], np.arange(0, n - 1, dtype=np.int32)))
    next_idx = np.concatenate((np.arange(1, n, dtype=np.int32), [n - 1]))
    mixed = rgb * (1.0 - 2.0 * s) + rgb[prev_idx] * s + rgb[next_idx] * s
    return mixed.astype(np.float32)


def _sample_gradient_rgb(stops_lin: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Sample multi-stop linear-space gradient at positions ``t`` in [0, 1]."""
    tt = np.clip(np.asarray(t, dtype=np.float32), 0.0, 1.0)
    n = int(tt.shape[0])
    if stops_lin.shape[0] < 2:
        rgb = np.repeat(stops_lin[:1], n, axis=0)
        return _linear_to_srgb(rgb)
    segment_count = int(stops_lin.shape[0] - 1)
    scaled = tt * float(segment_count)
    seg_idx = np.minimum(segment_count - 1, np.floor(scaled).astype(np.int32))
    # Softer melt between stops — removes hard “joint” lines in fills.
    local_t = _smoothstep01(_smoothstep01(scaled - seg_idx.astype(np.float32))).reshape((n, 1))
    c1 = stops_lin[seg_idx]
    c2 = stops_lin[np.minimum(seg_idx + 1, stops_lin.shape[0] - 1)]
    rgb_lin = c1 * (1.0 - local_t) + c2 * local_t
    return _linear_to_srgb(rgb_lin)


def build_spectrum_vertex_rgba(
    *,
    mode: str,
    solid_color: str,
    gradient_colors: list[str] | None,
    count: int,
    alpha: float,
) -> np.ndarray:
    """Build per-bar RGBA colors for preview/export spectrum draws.

    Multi-stop gradients interpolate through every stop (not first→last only)
    for crystal-clear hue bands (no soft wash / neighbor blur).
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
            rgb = _sample_gradient_rgb(stops_lin, t)
            alpha_col = np.full((n, 1), a, dtype=np.float32)
            return np.concatenate([rgb.astype(np.float32), alpha_col], axis=1)

    base = _hex_to_rgb01(solid_color)
    return np.tile(np.array([base[0], base[1], base[2], a], dtype=np.float32)[None, :], (n, 1))


def build_spectrum_fill_fan_rgba(
    *,
    xs_ndc: np.ndarray,
    ys_ndc: np.ndarray,
    mode: str,
    solid_color: str,
    gradient_colors: list[str] | None,
    alpha: float,
    gradient_direction: str = "left-to-right",
    close_loop: bool = False,
) -> np.ndarray:
    """RGBA for a TRIANGLE_FAN fill (center + edge ring) with a smooth spatial melt.

    Colors sample the palette by screen position (not bar index), so left/right
    halves blend instead of meeting as a hard vertical joint. The center uses the
    mid-stop color. When ``close_loop`` is set, the duplicated closing edge vertex
    reuses the first edge color (no wrap seam).
    """
    xs = np.asarray(xs_ndc, dtype=np.float32).reshape(-1)
    ys = np.asarray(ys_ndc, dtype=np.float32).reshape(-1)
    tip_n = int(xs.shape[0])
    a = float(max(0.0, min(1.0, alpha)))
    if tip_n <= 0:
        return np.zeros((1, 4), dtype=np.float32)

    direction = str(gradient_direction or "left-to-right").lower().strip()
    if direction in ("radial", "circular"):
        direction = "left-to-right"

    if str(mode or "solid").lower().strip() != "gradient":
        base = _hex_to_rgb01(solid_color)
        row = np.array([base[0], base[1], base[2], a], dtype=np.float32)
        return np.tile(row[None, :], (tip_n + 1, 1))

    stops_raw = [str(c).strip() for c in (gradient_colors or []) if str(c or "").strip()]
    stops_raw = normalize_spectrum_gradient_colors(stops_raw, solid_color or GRADIENT_FALLBACK_COLOR)
    stops = np.stack([_hex_to_rgb01(c) for c in stops_raw], axis=0).astype(np.float32)
    stops_lin = _srgb_to_linear(stops)

    # Spatial factor from edge positions (NDC −1…1 → 0…1).
    if direction == "top-to-bottom":
        t_edge = (1.0 - (ys + 1.0) * 0.5).astype(np.float32)
    elif direction == "diagonal":
        t_edge = ((xs + 1.0) * 0.5 * 0.55 + (1.0 - (ys + 1.0) * 0.5) * 0.45).astype(np.float32)
    else:
        t_edge = ((xs + 1.0) * 0.5).astype(np.float32)
    t_edge = np.clip(t_edge, 0.0, 1.0)

    # Widen the melt zone slightly so two-stop palettes don't read as a hard cut.
    t_edge = _smoothstep01(t_edge)

    edge_n = tip_n - 1 if close_loop and tip_n >= 2 else tip_n
    if close_loop and tip_n >= 2:
        rgb_core = _sample_gradient_rgb(stops_lin, t_edge[:edge_n])
        rgb_edge = np.concatenate([rgb_core, rgb_core[:1]], axis=0)
    else:
        rgb_edge = _sample_gradient_rgb(stops_lin, t_edge)

    # Center = true mid palette (melts both sides together, no single-stop pie).
    mid_rgb = _sample_gradient_rgb(stops_lin, np.asarray([0.5], dtype=np.float32))[0]
    alpha_col = np.full((tip_n, 1), a, dtype=np.float32)
    edge = np.concatenate([rgb_edge.astype(np.float32), alpha_col], axis=1)
    center = np.array([[mid_rgb[0], mid_rgb[1], mid_rgb[2], a]], dtype=np.float32)
    return np.concatenate([center, edge], axis=0)


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
