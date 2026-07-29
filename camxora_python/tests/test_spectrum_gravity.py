"""Tests for spectrum bar-growth directions: Top / Bottom / Left / Right."""

from __future__ import annotations

import numpy as np

from features.video.widgets.spectrum_layer_editor import GRAVITY_OPTIONS
from visualizer._spectrum_fast import (
    clamp_spectrum_bar_count,
    generate_points_curved,
    generate_points_linear,
    normalize_spectrum_gravity,
    resample_fft_bins,
    resolve_curved_spectrum_basis,
    resolve_spectrum_growth_direction,
)
from visualizer.template_runtime import normalize_renderer_template


def test_gravity_options_are_four_directions_only() -> None:
    values = [value for value, _label in GRAVITY_OPTIONS]
    assert values == ["top", "bottom", "left", "right"]
    assert "normal" not in values


def test_normalize_maps_legacy_normal_to_top() -> None:
    assert normalize_spectrum_gravity("normal") == "top"
    assert normalize_spectrum_gravity("BOTTOM") == "bottom"


def test_linear_directions_raise_as_labeled() -> None:
    _px, _py, dx, dy = generate_points_linear(8, 100.0, "top")
    assert np.allclose(dx, 0.0) and np.allclose(dy, 1.0)

    _px, _py, dx, dy = generate_points_linear(8, 100.0, "bottom")
    assert np.allclose(dx, 0.0) and np.allclose(dy, -1.0)

    _px, _py, dx, dy = generate_points_linear(8, 100.0, "left")
    assert np.allclose(dx, -1.0) and np.allclose(dy, 0.0)

    _px, _py, dx, dy = generate_points_linear(8, 100.0, "right")
    assert np.allclose(dx, 1.0) and np.allclose(dy, 0.0)


def test_curved_directions_raise_uniformly() -> None:
    for gravity, expect_dx, expect_dy in (
        ("top", 0.0, 1.0),
        ("bottom", 0.0, -1.0),
        ("left", -1.0, 0.0),
        ("right", 1.0, 0.0),
    ):
        start, gdx, gdy = resolve_curved_spectrum_basis(gravity)
        assert (gdx, gdy) == resolve_spectrum_growth_direction(gravity)
        assert (gdx, gdy) == (expect_dx, expect_dy)
        _px, _py, dx, dy = generate_points_curved(16, 100.0, True, start, gdx, gdy)
        assert np.allclose(dx, expect_dx)
        assert np.allclose(dy, expect_dy)


def test_semi_circle_sits_on_chosen_side() -> None:
    start_t, gdx_t, gdy_t = resolve_curved_spectrum_basis("top")
    _px, py, _dx, _dy = generate_points_curved(32, 100.0, False, start_t, gdx_t, gdy_t)
    assert float(np.mean(py)) > 0.0

    start_b, gdx_b, gdy_b = resolve_curved_spectrum_basis("bottom")
    _px, py, _dx, _dy = generate_points_curved(32, 100.0, False, start_b, gdx_b, gdy_b)
    assert float(np.mean(py)) < 0.0


def test_align_style_geometry_does_not_overwrite_user_gravity() -> None:
    from features.video.lib.spectrum_style_registry import align_spectrum_layers_to_style_geometry

    layers = [{"id": "l1", "gravity": "bottom", "curved": True, "mirrored": False}]
    aligned = align_spectrum_layers_to_style_geometry(layers, "orbit-spikes")
    assert aligned[0]["gravity"] == "bottom"


def test_normalize_accepts_top_gravity() -> None:
    tpl = normalize_renderer_template(
        {
            "style": "orbit-spikes",
            "layers": [{"gravity": "top", "barWidth": 5, "thickness": 30}],
        }
    )
    assert tpl["layers"][0]["gravity"] == "top"


def test_normalize_maps_legacy_normal_gravity() -> None:
    tpl = normalize_renderer_template(
        {
            "style": "orbit-spikes",
            "layers": [{"gravity": "normal", "barWidth": 5, "thickness": 30}],
        }
    )
    assert tpl["layers"][0]["gravity"] == "top"


def test_normalize_clamps_phase1_layer_fields() -> None:
    tpl = normalize_renderer_template(
        {
            "style": "orbit-spikes",
            "layers": [
                {
                    "barCount": 999,
                    "solidBand": True,
                    "peakCapsEnabled": True,
                    "peakCapGap": 99,
                    "peakCapThickness": 0.1,
                    "peakCapDecay": 0.1,
                }
            ],
        }
    )
    layer = tpl["layers"][0]
    assert layer["barCount"] == 192
    assert layer["solidBand"] is True
    assert layer["peakCapsEnabled"] is True
    assert layer["peakCapGap"] == 24.0
    assert layer["peakCapThickness"] == 1.0
    assert layer["peakCapDecay"] == 0.7


def test_bar_count_clamp_and_fft_resample() -> None:
    assert clamp_spectrum_bar_count(None) == 64
    assert clamp_spectrum_bar_count(2) == 16
    assert clamp_spectrum_bar_count(300) == 192
    src = np.linspace(0.0, 1.0, 64, dtype=np.float32)
    out = resample_fft_bins(src, 24)
    assert out.shape == (24,)
    assert float(out[0]) == 0.0
    assert float(out[-1]) == 1.0
