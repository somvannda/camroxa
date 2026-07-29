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


def resolve_curved_spectrum_basis(gravity: str) -> tuple[float, float]:
    """Return ``(start_angle, radial_sign)`` for curved spectrum layers.

    ``radial_sign`` is ``+1`` for outward growth (normal) and ``-1`` for inward
    growth (bottom / rabbit ears). For Curve 180, bottom also places the arc on
    the lower semicircle so growth toward center reads bottom→top.
    """
    g = str(gravity or "normal").lower().strip()
    start_angle = float(np.pi / 2.0)
    radial_sign = 1.0
    if g == "top":
        start_angle = float(-np.pi / 2.0)
    elif g == "left":
        start_angle = float(np.pi)
    elif g == "right":
        start_angle = 0.0
    elif g == "bottom":
        # Rabbit ears: grow inward. On the bottom of the ring that is bottom→top.
        start_angle = float(-np.pi / 2.0)
        radial_sign = -1.0
    return start_angle, radial_sign


def generate_points_curved(
    n: int,
    radius: float,
    mirrored: bool,
    start_angle: float,
    radial_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate curved spectrum point positions and directions (vectorized).

    Returns:
        (px, py, dx, dy) arrays of shape (n,) float32
    """
    t0 = np.linspace(0.0, 1.0, n, dtype=np.float32) if n > 1 else np.zeros(1, dtype=np.float32)
    total_angle = np.pi * 2.0 if mirrored else np.pi
    ang = start_angle - total_angle / 2.0 + t0 * total_angle
    cos_a = np.cos(ang).astype(np.float32)
    sin_a = np.sin(ang).astype(np.float32)
    sign = float(radial_sign)
    if sign >= 0.0:
        sign = 1.0
    else:
        sign = -1.0
    return cos_a * radius, sin_a * radius, cos_a * sign, sin_a * sign


def generate_points_linear(n: int, total_length: float, gravity: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate linear spectrum point positions and directions (vectorized).
    
    Returns:
        (px, py, dx, dy) arrays of shape (n,) float32
    """
    t0 = np.linspace(0.0, 1.0, n, dtype=np.float32) if n > 1 else np.zeros(1, dtype=np.float32)
    start_x = -total_length / 2.0
    off = start_x + t0 * total_length
    zeros = np.zeros(n, dtype=np.float32)
    ones = np.ones(n, dtype=np.float32)
    g = str(gravity or "normal").lower().strip()
    if g in ("normal", "top"):
        return off, zeros, zeros, ones
    if g == "bottom":
        return off, zeros, zeros, -ones
    if g == "left":
        return zeros, off, ones, zeros
    return zeros, off, -ones, zeros


def resolve_bar_pixel_width(pass_bar_width: float, slot_w: float) -> float:
    """Clamp bar width so bars don't overlap their neighbors too aggressively."""
    bw = float(max(1.0, pass_bar_width))
    if slot_w > 1.0:
        bw = float(min(bw, slot_w * 0.95))
    return bw


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
        needle = float(max(1.0, bw * 0.28))
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
        wx_n = wx * 1.2
        wy_n = wy * 1.2
        p0x = px - wx_n
        p0y = py - wy_n
        p1x = px + wx_n
        p1y = py + wy_n
        p2x = px + dx * h_val + wx_n
        p2y = py + dy * h_val + wy_n
        p3x = px + dx * h_val - wx_n
        p3y = py + dy * h_val - wy_n
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
