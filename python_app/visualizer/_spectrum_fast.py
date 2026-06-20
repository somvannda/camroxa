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


def generate_points_curved(n: int, radius: float, mirrored: bool, start_angle: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate curved spectrum point positions and directions (vectorized).
    
    Returns:
        (px, py, dx, dy) arrays of shape (n,) float32
    """
    total_angle = np.pi * 2.0 if mirrored else np.pi
    t = np.linspace(0.0, 1.0, n, dtype=np.float64)
    angles = start_angle - (total_angle / 2.0) + (t * total_angle)
    cos_a = np.cos(angles).astype(np.float32)
    sin_a = np.sin(angles).astype(np.float32)
    px = cos_a * radius
    py = sin_a * radius
    return px, py, cos_a, sin_a


def generate_points_linear(n: int, total_length: float, gravity: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate linear spectrum point positions and directions (vectorized).
    
    Returns:
        (px, py, dx, dy) arrays of shape (n,) float32
    """
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    offsets = -total_length / 2.0 + t * total_length
    zeros = np.zeros(n, dtype=np.float32)
    
    if gravity == "bottom":
        return offsets, zeros, zeros, np.full(n, -1.0, dtype=np.float32)
    elif gravity == "top":
        return offsets, zeros, zeros, np.full(n, 1.0, dtype=np.float32)
    elif gravity == "left":
        return zeros, offsets, np.full(n, 1.0, dtype=np.float32), zeros
    else:  # right
        return zeros, offsets, np.full(n, -1.0, dtype=np.float32), zeros


def build_waveform_vertices(
    px: np.ndarray, py: np.ndarray, dx: np.ndarray, dy: np.ndarray,
    val_arr: np.ndarray, cx: float, cy: float, w: int, h: int,
    style_preset: str, pass_bar_width: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build waveform-style outer/inner vertices (vectorized).
    
    Returns:
        (xs_o, ys_o, xs_i, ys_i) arrays in NDC coordinates
    """
    nn = len(px)
    h_val = np.maximum(2.0, val_arr[:nn]).astype(np.float32)
    
    inv_w = 2.0 / float(w)
    inv_h = 2.0 / float(h)
    
    if style_preset == "mountain":
        peak_h = h_val * 1.18
        inner_d = pass_bar_width * 0.10
        xs_o = (cx + px + dx * peak_h) * inv_w - 1.0
        ys_o = (cy + py + dy * peak_h) * inv_h - 1.0
        xs_i = (cx + px + dx * inner_d) * inv_w - 1.0
        ys_i = (cy + py + dy * inner_d) * inv_h - 1.0
    elif style_preset == "liquid":
        liquid_h = h_val * 0.92
        inner_pull = pass_bar_width * 0.68
        xs_o = (cx + px + dx * liquid_h) * inv_w - 1.0
        ys_o = (cy + py + dy * liquid_h) * inv_h - 1.0
        xs_i = (cx + px - dx * inner_pull) * inv_w - 1.0
        ys_i = (cy + py - dy * inner_pull) * inv_h - 1.0
    else:  # soft-waveform, continuous-waveform
        half_t = pass_bar_width * 0.5
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
) -> np.ndarray:
    """Build bar-style quad vertices as 6 triangles per bar (vectorized).
    
    Returns:
        pos: shape (n*6, 2) float32 in NDC coordinates
    """
    n = len(px)
    h_val = np.maximum(2.0, val_arr[:n]).astype(np.float32)
    
    # Base perpendicular half-widths
    wx = -dy * (bw / 2.0)
    wy = dx * (bw / 2.0)
    
    if style_preset == "symmetrical-bars":
        half_h = h_val / 2.0
        p0x = px - dx * half_h - wx
        p0y = py - dy * half_h - wy
        p1x = px - dx * half_h + wx
        p1y = py - dy * half_h + wy
        p2x = px + dx * half_h + wx
        p2y = py + dy * half_h + wy
        p3x = px + dx * half_h - wx
        p3y = py + dy * half_h - wy
    elif style_preset == "floating-blocks":
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
    elif style_preset == "pixel-bars":
        step = 20.0 * sf
        h_val = np.ceil(h_val / step) * step
        p0x = px - wx
        p0y = py - wy
        p1x = px + wx
        p1y = py + wy
        p2x = px + dx * h_val + wx
        p2y = py + dy * h_val + wy
        p3x = px + dx * h_val - wx
        p3y = py + dy * h_val - wy
    elif style_preset == "thin-lines":
        wx_t = -dy * (1.0 * sf)
        wy_t = dx * (1.0 * sf)
        p0x = px - wx_t
        p0y = py - wy_t
        p1x = px + wx_t
        p1y = py + wy_t
        p2x = px + dx * h_val + wx_t
        p2y = py + dy * h_val + wy_t
        p3x = px + dx * h_val - wx_t
        p3y = py + dy * h_val - wy_t
    elif style_preset == "neon-pulse":
        pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
        h_val = h_val * pulse
        wx_n = wx * 1.25
        wy_n = wy * 1.25
        p0x = px - wx_n
        p0y = py - wy_n
        p1x = px + wx_n
        p1y = py + wy_n
        p2x = px + dx * h_val + wx_n
        p2y = py + dy * h_val + wy_n
        p3x = px + dx * h_val - wx_n
        p3y = py + dy * h_val - wy_n
    elif style_preset == "dot-matrix":
        step = np.maximum(10.0 * sf, bw * 1.2)
        h_val = np.ceil(h_val / step) * step
        wx_d = -dy * np.maximum(1.5 * sf, bw * 0.45)
        wy_d = dx * np.maximum(1.5 * sf, bw * 0.45)
        p0x = px - wx_d
        p0y = py - wy_d
        p1x = px + wx_d
        p1y = py + wy_d
        p2x = px + dx * h_val + wx_d
        p2y = py + dy * h_val + wy_d
        p3x = px + dx * h_val - wx_d
        p3y = py + dy * h_val - wy_d
    else:  # classic-vertical and default
        p0x = px - wx
        p0y = py - wy
        p1x = px + wx
        p1y = py + wy
        p2x = px + dx * h_val + wx
        p2y = py + dy * h_val + wy
        p3x = px + dx * h_val - wx
        p3y = py + dy * h_val - wy
    
    # Convert to NDC: (cx + p) / w * 2.0 - 1.0
    inv_w = 2.0 / float(w)
    inv_h = 2.0 / float(h)
    
    # Build 6 vertices per bar: triangle 1 = (p0, p1, p2), triangle 2 = (p0, p2, p3)
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
