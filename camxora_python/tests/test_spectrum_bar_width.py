"""Tests for spectrum bar-width pixel mapping and density limits."""

from __future__ import annotations

from visualizer_video._spectrum_fast import (
    _BAR_MIN_GAP_PX,
    _BAR_SLOT_MAX_FILL,
    _MAX_BAR_COUNT,
    clamp_spectrum_bar_count,
    resolve_bar_pixel_width,
)
from visualizer_video.gpu_render import _audio_bar_height_mult


def test_resolve_bar_pixel_width_uses_slider_value_when_no_slot() -> None:
    assert resolve_bar_pixel_width(1.0) == 1.0
    assert resolve_bar_pixel_width(7.5) == 7.5
    assert resolve_bar_pixel_width(40.0) == 40.0
    assert resolve_bar_pixel_width(0.4) == 0.4


def test_resolve_bar_pixel_width_reserves_gap_inside_slot() -> None:
    slot = 20.0
    max_bw = max(1.0, slot - max(_BAR_MIN_GAP_PX, slot * (1.0 - _BAR_SLOT_MAX_FILL)))
    assert resolve_bar_pixel_width(100.0, slot_width=slot) == max_bw
    assert resolve_bar_pixel_width(5.0, slot) == 5.0
    assert resolve_bar_pixel_width(1.0, 10.0) == 1.0
    # Higher density => smaller slots => tighter width ceiling.
    wide_slot = resolve_bar_pixel_width(100.0, 40.0)
    narrow_slot = resolve_bar_pixel_width(100.0, 10.0)
    assert wide_slot > narrow_slot
    assert wide_slot < 40.0
    assert narrow_slot < 10.0


def test_audio_bar_height_mult_scales_spike_height() -> None:
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 1.0}}) == 1.0
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 2.5}}) == 2.5
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 0.1}}) == 0.25
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 99.0}}) == 12.0
    assert _audio_bar_height_mult({}) == 1.0


def test_bar_density_allows_up_to_192() -> None:
    assert _MAX_BAR_COUNT == 192
    assert clamp_spectrum_bar_count(None) == 64
    assert clamp_spectrum_bar_count(2) == 16
    assert clamp_spectrum_bar_count(128) == 128
    assert clamp_spectrum_bar_count(192) == 192
    assert clamp_spectrum_bar_count(300) == 192


def test_classic_bars_tip_taper_control() -> None:
    """Tip taper 0 = equal width; tip taper 1 = narrower tip."""
    import numpy as np

    from visualizer_video._spectrum_fast import build_bar_vertices

    n = 4
    px = np.zeros(n, dtype=np.float32)
    py = np.zeros(n, dtype=np.float32)
    dx = np.zeros(n, dtype=np.float32)
    dy = np.ones(n, dtype=np.float32)
    val = np.full(n, 40.0, dtype=np.float32)
    equal = build_bar_vertices(
        px, py, dx, dy, val, 100.0, 100.0, 200, 200, 10.0, "orbit-spikes", 1.0, tip_taper=0.0
    )
    tapered = build_bar_vertices(
        px, py, dx, dy, val, 100.0, 100.0, 200, 200, 10.0, "orbit-spikes", 1.0, tip_taper=1.0
    )
    eq_base = abs(float(equal[1, 0] - equal[0, 0]))
    eq_tip = abs(float(equal[2, 0] - equal[5, 0]))
    tap_base = abs(float(tapered[1, 0] - tapered[0, 0]))
    tap_tip = abs(float(tapered[2, 0] - tapered[5, 0]))
    assert abs(eq_tip - eq_base) < 1e-5
    assert tap_tip < tap_base * 0.7
    assert tap_tip > tap_base * 0.35
