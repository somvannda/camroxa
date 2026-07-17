"""Tests for spectrum bar-width pixel mapping."""

from __future__ import annotations

from visualizer._spectrum_fast import resolve_bar_pixel_width
from visualizer.gpu_render import _audio_bar_height_mult


def test_resolve_bar_pixel_width_uses_slider_value_directly() -> None:
    assert resolve_bar_pixel_width(1.0) == 1.0
    assert resolve_bar_pixel_width(7.5) == 7.5
    assert resolve_bar_pixel_width(40.0) == 40.0
    # Slot width no longer soft-caps the slider.
    assert resolve_bar_pixel_width(100.0, slot_width=20.0) == 100.0


def test_audio_bar_height_mult_scales_spike_height() -> None:
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 1.0}}) == 1.0
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 2.5}}) == 2.5
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 0.1}}) == 0.25
    assert _audio_bar_height_mult({"audioSettings": {"barHeight": 99.0}}) == 8.0
    assert _audio_bar_height_mult({}) == 1.0
