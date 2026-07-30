"""Tests for spectrum bar-width pixel mapping and density limits."""

from __future__ import annotations

from visualizer._spectrum_fast import (
    _BAR_MIN_GAP_PX,
    _BAR_SLOT_MAX_FILL,
    _MAX_BAR_COUNT,
    clamp_spectrum_bar_count,
    resolve_bar_pixel_width,
)
from visualizer.gpu_render import _audio_bar_height_mult


def test_resolve_bar_pixel_width_uses_slider_value_when_no_slot() -> None:
    assert resolve_bar_pixel_width(1.0) == 1.0
    assert resolve_bar_pixel_width(7.5) == 7.5
    assert resolve_bar_pixel_width(40.0) == 40.0


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
