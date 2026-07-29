"""Vectorized spectrum rendering helpers for the GPU render loop.

Replaces per-element Python loops with numpy operations for ~10-20x speedup
on the per-frame spectrum computation hot path.
"""
from __future__ import annotations

import numpy as np

# Pre-computed constants
_BINS = 64
_SAMPLE_RATE = 44100.0
_NYQUIST = _SAMPLE_RATE / 2.0
_MIN_FREQ = 20.0
_MAX_FREQ = 12000.0
_MIN_LOG = np.log10(_MIN_FREQ)
_MAX_LOG = np.log10(_MAX_FREQ)

# Pre-compute the log-frequency bin indices and interpolation weights (never changes)
_bin_indices = np.arange(_BINS, dtype=np.float64)
_log_freqs = _MIN_LOG + (_bin_indices / float(_BINS)) * (_MAX_LOG - _MIN_LOG)
_freqs = 10.0 ** _log_freqs
_freq_boost = (1.0 + ((_bin_indices / float(_BINS)) ** 2) * 2.0).astype(np.float32)

# 5-tap convolution kernel
_SMOOTH_KERNEL = np.array([0.1, 0.2, 0.4, 0.2, 0.1], dtype=np.float32)

_MIN_BAR_COUNT = 16
_MAX_BAR_COUNT = 192
# Leave headroom between bars so density + width do not melt into a solid wall.
_BAR_SLOT_MAX_FILL = 0.72
_BAR_MIN_GAP_PX = 2.0


def precompute_fft_mapping(point_count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pre-compute FFT bin mapping arrays (call once at startup).
    
    Returns:
        (idx1, idx2, frac) arrays of shape (BINS,)
    """
    fft_size_half = float(point_count)
    linear_indices = (_freqs / _NYQUIST) * fft_size_half
    idx1 = np.floor(linear_indices).astype(np.int32)
    idx2 = np.minimum(np.ceil(linear_indices).astype(np.int32), int(fft_size_half) - 1)
    frac = (linear_indices - idx1.astype(np.float64)).astype(np.float32)
    return idx1, idx2, frac


def fft_to_log_bins(fft: np.ndarray, idx1: np.ndarray, idx2: np.ndarray, frac: np.ndarray) -> np.ndarray:
    """Map raw FFT to 64 logarithmic bins (vectorized).
    
    Args:
        fft: Raw FFT array from AudioAnalyzer
        idx1, idx2, frac: Pre-computed mapping from precompute_fft_mapping()
    
    Returns:
        fft_log: shape (64,) float32, clamped to [0.01, 1.0]
    """
    n0 = fft.shape[0]
    # Safe indexing — clamp to valid range
    safe_idx1 = np.minimum(idx1, n0 - 1)
    safe_idx2 = np.minimum(idx2, n0 - 1)
    mask1 = idx1 < n0
    mask2 = idx2 < n0
    
    val1 = np.where(mask1, fft[safe_idx1], 0.0).astype(np.float32)
    val2 = np.where(mask2, fft[safe_idx2], 0.0).astype(np.float32)
    
    raw_val = val1 * (1.0 - frac) + val2 * frac
    result = raw_val * _freq_boost
    return np.clip(result, 0.01, 1.0)


def smooth_fft_envelope(prev: np.ndarray, target: np.ndarray, smoothing: float) -> np.ndarray:
    """Exponential smooth of log FFT bins (shared by preview paintGL and export)."""
    s = float(max(0.0, min(0.99, smoothing)))
    return (prev * s + target * (1.0 - s)).astype(np.float32)


def smooth_and_mirror(fft_s: np.ndarray, mirrored: bool) -> np.ndarray:
    """Apply 5-tap smoothing and optional mirroring (vectorized).
    
    Args:
        fft_s: Gain-adjusted FFT, shape (64,) float32
        mirrored: Whether to mirror the spectrum
    
    Returns:
        render_fft: shape (64,) float32
    """
    # Full convolution with 'same' mode handles the 5-tap smoothing
    smoothed = np.convolve(fft_s, _SMOOTH_KERNEL, mode='same').astype(np.float32)
    # Edge bins keep original values (convolution boundary effects)
    smoothed[0] = fft_s[0]
    smoothed[1] = fft_s[1]
    smoothed[-1] = fft_s[-1]
    smoothed[-2] = fft_s[-2]
    
    if mirrored:
        half = _BINS // 2
        left = smoothed[:half]
        render_fft = np.empty(_BINS, dtype=np.float32)
        render_fft[:half] = left[::-1]
        render_fft[half:] = left
        return render_fft
    return smoothed


def clamp_spectrum_bar_count(value: float | int | None, default: int = _BINS) -> int:
    try:
        n = int(round(float(value if value is not None else default)))
    except (TypeError, ValueError):
        n = int(default)
    return int(max(_MIN_BAR_COUNT, min(_MAX_BAR_COUNT, n)))


def resample_fft_bins(render_fft: np.ndarray, count: int) -> np.ndarray:
    n = clamp_spectrum_bar_count(count)
    src = np.asarray(render_fft, dtype=np.float32).reshape(-1)
    if src.shape[0] <= 0:
        return np.zeros((n,), dtype=np.float32)
    if src.shape[0] == n:
        return src.astype(np.float32)
    x_src = np.linspace(0.0, 1.0, src.shape[0], dtype=np.float32)
    x_dst = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return np.interp(x_dst, x_src, src).astype(np.float32)


def normalize_spectrum_gravity(gravity: str | None) -> str:
    """Map gravity to Top / Bottom / Left / Right / Outward / Inward."""
    g = str(gravity or "top").lower().strip()
    if g == "normal":
        return "top"
    if g in ("outside", "out", "radial-out", "radial_out"):
        return "outward"
    if g in ("inside", "in", "radial-in", "radial_in"):
        return "inward"
    if g in ("top", "bottom", "left", "right", "outward", "inward"):
        return g
    return "top"


def is_radial_spectrum_gravity(gravity: str | None) -> bool:
    return normalize_spectrum_gravity(gravity) in ("outward", "inward")


def resolve_spectrum_growth_direction(gravity: str | None) -> tuple[float, float]:
    """Return screen-space ``(dx, dy)`` for linear / uniform raise.

    On a curved ring, Top/Left/Right/Bottom and radial modes use per-bar
    facing normals from ``generate_points_curved`` instead of this vector.
    """
    g = normalize_spectrum_gravity(gravity)
    if g == "bottom":
        return (0.0, -1.0)
    if g == "left":
        return (-1.0, 0.0)
    if g == "right":
        return (1.0, 0.0)
    if g in ("outward", "inward"):
        return (0.0, 0.0)
    return (0.0, 1.0)


def resolve_curved_spectrum_basis(gravity: str | None) -> tuple[float, float, float]:
    """Return ``(start_angle, growth_dx, growth_dy)`` for curved spectrum layers.

    Top/Bottom/Left/Right choose which arc the bars sit on. Raise direction is
    per-bar facing (radial) in ``generate_points_curved``. Outside/Inside use a
    full-ring layout with out/in facing.
    """
    g = normalize_spectrum_gravity(gravity)
    growth_dx, growth_dy = resolve_spectrum_growth_direction(g)
    if g in ("outward", "inward"):
        return float(np.pi / 2.0), float(growth_dx), float(growth_dy)
    if g == "bottom":
        start_angle = float(-np.pi / 2.0)
    elif g == "left":
        start_angle = float(np.pi)
    elif g == "right":
        start_angle = 0.0
    else:
        start_angle = float(np.pi / 2.0)
    return start_angle, float(growth_dx), float(growth_dy)


def generate_points_curved(
    n: int,
    radius: float,
    mirrored: bool,
    start_angle: float,
    growth_dx: float = 0.0,
    growth_dy: float = 1.0,
    gravity: str | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate curved spectrum point positions and raise directions.

    Returns:
        (px, py, dx, dy) arrays of shape (n,) float32

    Bars raise along the direction they face on the ring:
    - ``outward`` / Top/Bottom/Left/Right → radially out
    - ``inward`` → radially in
    """
    t0 = np.linspace(0.0, 1.0, n, dtype=np.float32) if n > 1 else np.zeros(1, dtype=np.float32)
    total_angle = np.pi * 2.0 if mirrored else np.pi
    ang = start_angle - total_angle / 2.0 + t0 * total_angle
    cos_a = np.cos(ang).astype(np.float32)
    sin_a = np.sin(ang).astype(np.float32)
    g = normalize_spectrum_gravity(gravity) if gravity is not None else None
    if g is None:
        # Legacy callers without gravity: keep uniform growth_dx/growth_dy.
        gdx = float(growth_dx)
        gdy = float(growth_dy)
        length = float(np.hypot(gdx, gdy))
        if length <= 1e-6:
            gdx, gdy = 0.0, 1.0
        else:
            gdx /= length
            gdy /= length
        return (
            cos_a * radius,
            sin_a * radius,
            np.full(n, gdx, dtype=np.float32),
            np.full(n, gdy, dtype=np.float32),
        )
    if g == "inward":
        return cos_a * radius, sin_a * radius, (-cos_a).astype(np.float32), (-sin_a).astype(np.float32)
    # outward + top/bottom/left/right: each bar raises the way it faces (out).
    return cos_a * radius, sin_a * radius, cos_a, sin_a


def generate_points_linear(n: int, total_length: float, gravity: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate linear spectrum point positions and raise directions.

    Returns:
        (px, py, dx, dy) arrays of shape (n,) float32
    """
    t0 = np.linspace(0.0, 1.0, n, dtype=np.float32) if n > 1 else np.zeros(1, dtype=np.float32)
    start_x = -total_length / 2.0
    off = start_x + t0 * total_length
    zeros = np.zeros(n, dtype=np.float32)
    g = normalize_spectrum_gravity(gravity)
    # Radial modes have no meaning on a straight row — treat as Top.
    if g in ("outward", "inward"):
        g = "top"
    gdx, gdy = resolve_spectrum_growth_direction(g)
    # Baseline is perpendicular to raise direction.
    if g in ("left", "right"):
        return zeros, off, np.full(n, gdx, dtype=np.float32), np.full(n, gdy, dtype=np.float32)
    return off, zeros, np.full(n, gdx, dtype=np.float32), np.full(n, gdy, dtype=np.float32)


def normalize_spectrum_path_mode(path_mode: str | None) -> str:
    """Normalize layer ``pathMode`` to ``auto`` | ``circle`` | ``rect``."""
    v = str(path_mode or "auto").lower().strip()
    if v in ("rectangle", "square"):
        return "rect"
    if v in ("auto", "circle", "rect"):
        return v
    return "auto"


def resolve_spectrum_path_mode(
    path_mode: str | None,
    *,
    curved: bool,
    attached_to_logo: bool,
    logo_shape: str | None,
) -> str:
    """Resolve geometry path: ``linear`` | ``circle`` | ``rect``."""
    if not curved:
        return "linear"
    mode = normalize_spectrum_path_mode(path_mode)
    if mode == "auto":
        shape = str(logo_shape or "circle").lower().strip()
        if attached_to_logo and shape in ("square", "rect", "rectangle"):
            return "rect"
        return "circle"
    return mode


def rect_path_length(half_w: float, half_h: float, mirrored: bool, gravity: str | None) -> float:
    hw = float(max(1.0, half_w))
    hh = float(max(1.0, half_h))
    g = normalize_spectrum_gravity(gravity)
    if mirrored or g in ("outward", "inward"):
        return float(2.0 * (2.0 * hw + 2.0 * hh))
    if g in ("left", "right"):
        return float(2.0 * hh)
    return float(2.0 * hw)


def generate_points_rect(
    n: int,
    half_w: float,
    half_h: float,
    mirrored: bool,
    gravity: str | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample a rectangle perimeter; raise directions are edge normals.

    Full circle form (``mirrored``) walks the whole perimeter. Circle Raise
    (semi) samples only the edge matching Bar Growth. Radial outward/inward
    always walk the full perimeter (spikes around the square).
    """
    nn = int(max(1, n))
    hw = float(max(1.0, half_w))
    hh = float(max(1.0, half_h))
    g = normalize_spectrum_gravity(gravity)
    t0 = np.linspace(0.0, 1.0, nn, dtype=np.float32) if nn > 1 else np.zeros(1, dtype=np.float32)
    radial = g in ("outward", "inward")

    if not mirrored and not radial:
        if g == "bottom":
            px = (hw - t0 * (2.0 * hw)).astype(np.float32)
            py = np.full(nn, -hh, dtype=np.float32)
            return px, py, np.zeros(nn, dtype=np.float32), np.full(nn, -1.0, dtype=np.float32)
        if g == "left":
            px = np.full(nn, -hw, dtype=np.float32)
            py = (hh - t0 * (2.0 * hh)).astype(np.float32)
            return px, py, np.full(nn, -1.0, dtype=np.float32), np.zeros(nn, dtype=np.float32)
        if g == "right":
            px = np.full(nn, hw, dtype=np.float32)
            py = (-hh + t0 * (2.0 * hh)).astype(np.float32)
            return px, py, np.full(nn, 1.0, dtype=np.float32), np.zeros(nn, dtype=np.float32)
        px = (-hw + t0 * (2.0 * hw)).astype(np.float32)
        py = np.full(nn, hh, dtype=np.float32)
        return px, py, np.zeros(nn, dtype=np.float32), np.full(nn, 1.0, dtype=np.float32)

    top_len = 2.0 * hw
    right_len = 2.0 * hh
    bottom_len = 2.0 * hw
    left_len = 2.0 * hh
    peri = top_len + right_len + bottom_len + left_len
    # Start at the midpoint of the gravity edge so bass lands on that side.
    if g == "bottom":
        start = top_len + right_len + bottom_len * 0.5
    elif g == "left":
        start = top_len + right_len + bottom_len + left_len * 0.5
    elif g == "right":
        start = top_len + right_len * 0.5
    else:
        start = top_len * 0.5

    # endpoint=False avoids duplicating the seam; callers may close waveform rings.
    s = (start + np.linspace(0.0, peri, nn, endpoint=False, dtype=np.float64)) % peri
    px = np.empty(nn, dtype=np.float32)
    py = np.empty(nn, dtype=np.float32)
    dx = np.empty(nn, dtype=np.float32)
    dy = np.empty(nn, dtype=np.float32)
    c1 = top_len
    c2 = c1 + right_len
    c3 = c2 + bottom_len
    for i in range(nn):
        d = float(s[i])
        if d < c1:
            u = d / top_len if top_len > 1e-6 else 0.0
            px[i] = float(-hw + u * 2.0 * hw)
            py[i] = hh
            dx[i], dy[i] = 0.0, 1.0
        elif d < c2:
            u = (d - c1) / right_len if right_len > 1e-6 else 0.0
            px[i] = hw
            py[i] = float(hh - u * 2.0 * hh)
            dx[i], dy[i] = 1.0, 0.0
        elif d < c3:
            u = (d - c2) / bottom_len if bottom_len > 1e-6 else 0.0
            px[i] = float(hw - u * 2.0 * hw)
            py[i] = -hh
            dx[i], dy[i] = 0.0, -1.0
        else:
            u = (d - c3) / left_len if left_len > 1e-6 else 0.0
            px[i] = -hw
            py[i] = float(-hh + u * 2.0 * hh)
            dx[i], dy[i] = -1.0, 0.0
    if g == "inward":
        dx = (-dx).astype(np.float32)
        dy = (-dy).astype(np.float32)
    return px, py, dx, dy


def generate_spectrum_layer_geometry(
    n: int,
    *,
    curved: bool,
    mirrored: bool,
    gravity: str | None,
    path_mode: str | None,
    radius: float,
    half_w: float | None = None,
    half_h: float | None = None,
    attached_to_logo: bool = False,
    logo_shape: str | None = None,
    frame_w: int = 1920,
    frame_h: int = 1080,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Build bar bases for a layer.

    Returns:
        ``(px, py, dx, dy, path_length)``
    """
    path = resolve_spectrum_path_mode(
        path_mode,
        curved=bool(curved),
        attached_to_logo=bool(attached_to_logo),
        logo_shape=logo_shape,
    )
    g = normalize_spectrum_gravity(gravity)
    hw = float(half_w if half_w is not None else radius)
    hh = float(half_h if half_h is not None else radius)
    if path == "linear":
        total = float(frame_h * 0.8) if g in ("left", "right") else float(frame_w * 0.8)
        px, py, dx, dy = generate_points_linear(n, total, g)
        return px, py, dx, dy, float(total)
    if path == "rect":
        # Radial spikes always wrap the full rectangle perimeter.
        rect_mirrored = bool(mirrored) or g in ("outward", "inward")
        px, py, dx, dy = generate_points_rect(n, hw, hh, rect_mirrored, g)
        total = rect_path_length(hw, hh, rect_mirrored, g)
        return px, py, dx, dy, float(total)
    # Circle path: radial modes look best on a full ring — keep caller's
    # mirrored flag so Circle Raise 180° still works as a semi-arc.
    start_angle, growth_dx, growth_dy = resolve_curved_spectrum_basis(g)
    px, py, dx, dy = generate_points_curved(
        n,
        float(radius),
        bool(mirrored),
        start_angle,
        growth_dx,
        growth_dy,
        gravity=g,
    )
    total = float(radius) * (np.pi * 2.0 if mirrored else np.pi)
    return px, py, dx, dy, float(total)


def resolve_bar_pixel_width(
    pass_bar_width: float,
    slot_w: float = 0.0,
    *,
    slot_width: float | None = None,
    max_fill: float = _BAR_SLOT_MAX_FILL,
    min_gap_px: float = _BAR_MIN_GAP_PX,
) -> float:
    """Map bar-width slider to pixels, reserving a visible gap between bars.

    Density chooses how many slots fit along the ring/row. Width fills inside
    each slot. Past the gap-reserved max, width is clamped so bars stay separated
    (higher density => smaller usable width).
    """
    bw = float(max(1.0, pass_bar_width))
    slot = float(slot_width if slot_width is not None else slot_w)
    if slot > 1.0:
        fill = float(max(0.35, min(0.95, max_fill)))
        gap = float(max(min_gap_px, slot * (1.0 - fill)))
        max_bw = float(max(1.0, slot - gap))
        bw = float(min(bw, max_bw))
    return bw


def build_solid_band_strip_vertices(
    px: np.ndarray,
    py: np.ndarray,
    dx: np.ndarray,
    dy: np.ndarray,
    *,
    cx: float,
    cy: float,
    w: int,
    h: int,
    band_width_px: float,
) -> np.ndarray:
    """Build a ring/line strip under bars for ``solidBand`` layers."""
    nn = int(len(px))
    if nn <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    half = float(max(0.5, band_width_px * 0.5))
    wx = -dy * half
    wy = dx * half
    inv_w = 2.0 / float(max(1, w))
    inv_h = 2.0 / float(max(1, h))
    xs_l = (cx + px - wx) * inv_w - 1.0
    ys_l = (cy + py - wy) * inv_h - 1.0
    xs_r = (cx + px + wx) * inv_w - 1.0
    ys_r = (cy + py + wy) * inv_h - 1.0
    pos = np.empty((nn * 2, 2), dtype=np.float32)
    pos[0::2, 0] = xs_l
    pos[0::2, 1] = ys_l
    pos[1::2, 0] = xs_r
    pos[1::2, 1] = ys_r
    return pos


def mirror_spectrum_points_vertical(
    px: np.ndarray,
    py: np.ndarray,
    dx: np.ndarray,
    dy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Mirror spectrum bases across the horizontal axis through the layer origin."""
    return (
        np.asarray(px, dtype=np.float32).copy(),
        (-np.asarray(py, dtype=np.float32)).astype(np.float32),
        np.asarray(dx, dtype=np.float32).copy(),
        (-np.asarray(dy, dtype=np.float32)).astype(np.float32),
    )


def build_contour_wave_strips(
    px: np.ndarray,
    py: np.ndarray,
    dx: np.ndarray,
    dy: np.ndarray,
    val_arr: np.ndarray,
    cx: float,
    cy: float,
    w: int,
    h: int,
    *,
    line_count: int = 5,
    line_half_px: float = 1.35,
) -> list[np.ndarray]:
    """Build multi-line outlined contour strips (radio-wave look).

    Returns a list of NDC TRIANGLE_STRIP position arrays shaped ``(nn*2, 2)``.
    """
    nn = int(len(px))
    if nn <= 0:
        return []
    count = int(max(3, min(8, line_count)))
    half = float(max(0.6, line_half_px))
    h_val = np.maximum(1.5, np.asarray(val_arr[:nn], dtype=np.float32))
    inv_w = 2.0 / float(max(1, w))
    inv_h = 2.0 / float(max(1, h))
    px_a = np.asarray(px[:nn], dtype=np.float32)
    py_a = np.asarray(py[:nn], dtype=np.float32)
    dx_a = np.asarray(dx[:nn], dtype=np.float32)
    dy_a = np.asarray(dy[:nn], dtype=np.float32)
    strips: list[np.ndarray] = []
    for i in range(count):
        # Inner contours quieter; outer contour tracks full spike height.
        frac = float(i + 1) / float(count)
        scale = 0.22 + 0.78 * frac
        tip = h_val * scale
        xs_o = (cx + px_a + dx_a * (tip + half)) * inv_w - 1.0
        ys_o = (cy + py_a + dy_a * (tip + half)) * inv_h - 1.0
        xs_i = (cx + px_a + dx_a * (tip - half)) * inv_w - 1.0
        ys_i = (cy + py_a + dy_a * (tip - half)) * inv_h - 1.0
        pos = np.empty((nn * 2, 2), dtype=np.float32)
        pos[0::2, 0] = xs_o
        pos[0::2, 1] = ys_o
        pos[1::2, 0] = xs_i
        pos[1::2, 1] = ys_i
        strips.append(pos)
    return strips


def build_waveform_vertices(
    px: np.ndarray, py: np.ndarray, dx: np.ndarray, dy: np.ndarray,
    val_arr: np.ndarray, cx: float, cy: float, w: int, h: int,
    style_preset: str, pass_bar_width: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build waveform-style outer/inner vertices (vectorized).

    Camxora styles: aurora-ribbon, magma-ridge, plasma-bloom.
    Legacy aliases (soft-waveform/mountain/liquid) still accepted.
    """
    nn = len(px)
    h_val = np.maximum(2.0, val_arr[:nn]).astype(np.float32)

    inv_w = 2.0 / float(w)
    inv_h = 2.0 / float(h)
    style = str(style_preset or "").lower().strip()

    # Match live preview paintGL waveform math exactly.
    half_t = float(max(1.0, pass_bar_width)) * 0.5
    if style in ("magma-ridge", "mountain"):
        peak_h = h_val * 1.18
        shelf = half_t * 0.2
        xs_o = (cx + px + dx * peak_h) * inv_w - 1.0
        ys_o = (cy + py + dy * peak_h) * inv_h - 1.0
        xs_i = (cx + px + dx * shelf) * inv_w - 1.0
        ys_i = (cy + py + dy * shelf) * inv_h - 1.0
    elif style in ("plasma-bloom", "liquid"):
        bloom_h = h_val * 0.92
        inner_pull = half_t * 1.35
        xs_o = (cx + px + dx * bloom_h) * inv_w - 1.0
        ys_o = (cy + py + dy * bloom_h) * inv_h - 1.0
        xs_i = (cx + px - dx * inner_pull) * inv_w - 1.0
        ys_i = (cy + py - dy * inner_pull) * inv_h - 1.0
    else:
        # aurora-ribbon / soft-waveform / continuous-waveform
        xs_o = (cx + px + dx * (h_val + half_t)) * inv_w - 1.0
        ys_o = (cy + py + dy * (h_val + half_t)) * inv_h - 1.0
        xs_i = (cx + px + dx * (h_val - half_t)) * inv_w - 1.0
        ys_i = (cy + py + dy * (h_val - half_t)) * inv_h - 1.0

    return xs_o.astype(np.float32), ys_o.astype(np.float32), xs_i.astype(np.float32), ys_i.astype(np.float32)


def build_bar_vertices(
    px: np.ndarray, py: np.ndarray, dx: np.ndarray, dy: np.ndarray,
    val_arr: np.ndarray, cx: float, cy: float, w: int, h: int,
    bw: float, style_preset: str, sf: float,
    logo_audio_env: float = 0.0, particle_audio_env: float = 0.0,
    colors: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray] | np.ndarray:
    """Build bar-style quad vertices matching live preview paintGL geometry.

    When ``colors`` is provided, returns ``(pos, colsi)`` so variable-length
    styles (pulse-beads) can expand colors correctly. Without colors, returns
    ``pos`` only for backward compatibility (fixed 6 verts/bar styles).
    """
    n = len(px)
    h_val = np.maximum(2.0, val_arr[:n]).astype(np.float32)
    style = str(style_preset or "").lower().strip()

    wx = -dy * (bw / 2.0)
    wy = dx * (bw / 2.0)
    inv_w = 2.0 / float(w)
    inv_h = 2.0 / float(h)

    def _pack(p0x, p0y, p1x, p1y, p2x, p2y, p3x, p3y) -> np.ndarray:
        pos = np.empty((n * 6, 2), dtype=np.float32)
        ndc_p0x = (cx + p0x) * inv_w - 1.0
        ndc_p0y = (cy + p0y) * inv_h - 1.0
        ndc_p1x = (cx + p1x) * inv_w - 1.0
        ndc_p1y = (cy + p1y) * inv_h - 1.0
        ndc_p2x = (cx + p2x) * inv_w - 1.0
        ndc_p2y = (cy + p2y) * inv_h - 1.0
        ndc_p3x = (cx + p3x) * inv_w - 1.0
        ndc_p3y = (cy + p3y) * inv_h - 1.0
        pos[0::6, 0] = ndc_p0x
        pos[0::6, 1] = ndc_p0y
        pos[1::6, 0] = ndc_p1x
        pos[1::6, 1] = ndc_p1y
        pos[2::6, 0] = ndc_p2x
        pos[2::6, 1] = ndc_p2y
        pos[3::6, 0] = ndc_p0x
        pos[3::6, 1] = ndc_p0y
        pos[4::6, 0] = ndc_p2x
        pos[4::6, 1] = ndc_p2y
        pos[5::6, 0] = ndc_p3x
        pos[5::6, 1] = ndc_p3y
        return pos

    def _finish(pos: np.ndarray) -> tuple[np.ndarray, np.ndarray] | np.ndarray:
        if colors is None:
            return pos
        if pos.shape[0] == n * 6:
            colsi = np.repeat(colors[:n], 6, axis=0)
        else:
            # Variable verts (beads): expand colors by counting quads per bar.
            # Caller should pass colors and use the returned colsi.
            colsi = np.repeat(colors[:n], 6, axis=0)
            if colsi.shape[0] != pos.shape[0]:
                # Fallback: tile first color — beads path builds colsi itself.
                colsi = np.zeros((pos.shape[0], 4), dtype=np.float32)
        return pos, colsi.astype(np.float32)

    if style in ("pulse-beads", "dot-matrix"):
        pos_parts: list[np.ndarray] = []
        col_parts: list[np.ndarray] = []
        for i in range(n):
            h_i = float(h_val[i])
            dxi = float(dx[i])
            dyi = float(dy[i])
            wxi = float(wx[i])
            wyi = float(wy[i])
            pxi = float(px[i])
            pyi = float(py[i])
            dot_step = max(10.0 * sf, float(bw) * 1.2)
            dot_len = max(6.0 * sf, float(bw) * 0.9)
            seg_count = max(1, int(np.ceil(h_i / max(1.0, dot_step))))
            col_i = None
            if colors is not None and i < colors.shape[0]:
                col_i = colors[i]
            for seg in range(seg_count):
                seg_start = min(h_i, seg * dot_step)
                seg_end = min(h_i, seg_start + dot_len)
                if seg_end <= seg_start:
                    continue
                p0x = pxi + dxi * seg_start - wxi
                p0y = pyi + dyi * seg_start - wyi
                p1x = pxi + dxi * seg_start + wxi
                p1y = pyi + dyi * seg_start + wyi
                p2x = pxi + dxi * seg_end + wxi
                p2y = pyi + dyi * seg_end + wyi
                p3x = pxi + dxi * seg_end - wxi
                p3y = pyi + dyi * seg_end - wyi
                quad = np.array(
                    [
                        [(cx + p0x) * inv_w - 1.0, (cy + p0y) * inv_h - 1.0],
                        [(cx + p1x) * inv_w - 1.0, (cy + p1y) * inv_h - 1.0],
                        [(cx + p2x) * inv_w - 1.0, (cy + p2y) * inv_h - 1.0],
                        [(cx + p0x) * inv_w - 1.0, (cy + p0y) * inv_h - 1.0],
                        [(cx + p2x) * inv_w - 1.0, (cy + p2y) * inv_h - 1.0],
                        [(cx + p3x) * inv_w - 1.0, (cy + p3y) * inv_h - 1.0],
                    ],
                    dtype=np.float32,
                )
                pos_parts.append(quad)
                if col_i is not None:
                    col_parts.extend([col_i] * 6)
        if not pos_parts:
            empty = np.zeros((0, 2), dtype=np.float32)
            if colors is None:
                return empty
            return empty, np.zeros((0, 4), dtype=np.float32)
        pos = np.concatenate(pos_parts, axis=0)
        if colors is None:
            return pos
        if col_parts:
            return pos, np.asarray(col_parts, dtype=np.float32)
        return pos, np.zeros((pos.shape[0], 4), dtype=np.float32)

    if style in ("mirror-blades", "symmetrical-bars"):
        half_h = h_val * 0.5
        p0x = px - dx * half_h - wx
        p0y = py - dy * half_h - wy
        p1x = px - dx * half_h + wx
        p1y = py - dy * half_h + wy
        p2x = px + dx * half_h + wx
        p2y = py + dy * half_h + wy
        p3x = px + dx * half_h - wx
        p3y = py + dy * half_h - wy
    elif style in ("drift-capsules", "floating-blocks"):
        off1 = h_val + 20.0 * sf
        off2 = h_val + 30.0 * sf
        p0x = px + dx * off1 - wx
        p0y = py + dy * off1 - wy
        p1x = px + dx * off1 + wx
        p1y = py + dy * off1 + wy
        p2x = px + dx * off2 + wx
        p2y = py + dy * off2 + wy
        p3x = px + dx * off2 - wx
        p3y = py + dy * off2 - wy
    elif style in ("grid-steps", "pixel-bars"):
        step = 20.0 * sf
        h_val = np.ceil(h_val / np.maximum(1.0, step)) * np.maximum(1.0, step)
        p0x = px - wx
        p0y = py - wy
        p1x = px + wx
        p1y = py + wy
        p2x = px + dx * h_val + wx
        p2y = py + dy * h_val + wy
        p3x = px + dx * h_val - wx
        p3y = py + dy * h_val - wy
    elif style in ("signal-needles", "thin-lines"):
        # Keep needles thin vs classic bars, but still track Bar Width linearly.
        needle = float(max(1.0, bw * 0.55))
        wx_t = -dy * (needle / 2.0)
        wy_t = dx * (needle / 2.0)
        p0x = px - wx_t
        p0y = py - wy_t
        p1x = px + wx_t
        p1y = py + wy_t
        p2x = px + dx * h_val + wx_t
        p2y = py + dy * h_val + wy_t
        p3x = px + dx * h_val - wx_t
        p3y = py + dy * h_val - wy_t
    elif style in ("ignition-flare", "neon-pulse"):
        pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
        h_val = h_val * pulse
        # Tapered flare: wider base, sharper tip (less blocky than uniform width).
        wx_base = wx * 1.35
        wy_base = wy * 1.35
        wx_tip = wx * 0.55
        wy_tip = wy * 0.55
        p0x = px - wx_base
        p0y = py - wy_base
        p1x = px + wx_base
        p1y = py + wy_base
        p2x = px + dx * h_val + wx_tip
        p2y = py + dy * h_val + wy_tip
        p3x = px + dx * h_val - wx_tip
        p3y = py + dy * h_val - wy_tip
    else:
        # orbit-spikes / classic-vertical — match preview (no tip taper).
        p0x = px - wx
        p0y = py - wy
        p1x = px + wx
        p1y = py + wy
        p2x = px + dx * h_val + wx
        p2y = py + dy * h_val + wy
        p3x = px + dx * h_val - wx
        p3y = py + dy * h_val - wy

    pos = _pack(p0x, p0y, p1x, p1y, p2x, p2y, p3x, p3y)
    return _finish(pos)
