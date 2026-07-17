"""Tests for spectrum ring radius vs bar width separation."""

from __future__ import annotations

from visualizer.gpu_render import _resolve_spectrum_layer_radius


def test_bar_width_does_not_expand_ring_radius() -> None:
    base = _resolve_spectrum_layer_radius(
        attached_to_logo=False,
        attached_base_radius=0.0,
        attached_layer_base_offset=0.0,
        logo_visual_radius=100.0,
        bar_width=4.0,
        radius_offset=10.0,
    )
    wide = _resolve_spectrum_layer_radius(
        attached_to_logo=False,
        attached_base_radius=0.0,
        attached_layer_base_offset=0.0,
        logo_visual_radius=100.0,
        bar_width=80.0,
        radius_offset=10.0,
    )
    assert base == 110.0
    assert wide == 110.0


def test_layer_gap_still_expands_ring_radius() -> None:
    near = _resolve_spectrum_layer_radius(
        attached_to_logo=False,
        attached_base_radius=0.0,
        attached_layer_base_offset=0.0,
        logo_visual_radius=100.0,
        bar_width=8.0,
        radius_offset=0.0,
    )
    far = _resolve_spectrum_layer_radius(
        attached_to_logo=False,
        attached_base_radius=0.0,
        attached_layer_base_offset=0.0,
        logo_visual_radius=100.0,
        bar_width=8.0,
        radius_offset=40.0,
    )
    assert near == 100.0
    assert far == 140.0
