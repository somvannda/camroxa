"""Tests for spectrum gravity modes including Normal (straight rising)."""

from __future__ import annotations

import numpy as np

from features.video.widgets.spectrum_layer_editor import GRAVITY_OPTIONS
from visualizer._spectrum_fast import (
    clamp_spectrum_bar_count,
    generate_points_curved,
    generate_points_linear,
    resample_fft_bins,
    resolve_curved_spectrum_basis,
)
from visualizer.template_runtime import normalize_renderer_template


def test_gravity_options_include_normal_first() -> None:
    values = [value for value, _label in GRAVITY_OPTIONS]
    assert values[0] == "normal"
    assert "bottom" in values
    assert "top" in values


def test_normal_gravity_rises_upward_not_rabbit_ears() -> None:
    _px, _py, dx, dy = generate_points_linear(8, 100.0, "normal")
    assert np.allclose(dx, 0.0)
    assert np.allclose(dy, 1.0)

    _px_b, _py_b, dx_b, dy_b = generate_points_linear(8, 100.0, "bottom")
    assert np.allclose(dx_b, 0.0)
    assert np.allclose(dy_b, -1.0)


def test_curved_bottom_grows_inward_unlike_normal() -> None:
    start_n, sign_n = resolve_curved_spectrum_basis("normal")
    start_b, sign_b = resolve_curved_spectrum_basis("bottom")
    assert sign_n == 1.0
    assert sign_b == -1.0
    assert start_b == float(-np.pi / 2.0)

    px_b, py_b, dx_b, dy_b = generate_points_curved(16, 100.0, True, start_b, sign_b)
    px_n, py_n, dx_n, dy_n = generate_points_curved(16, 100.0, True, start_n, sign_n)

    # Bottom-most bar on rabbit-ears ring grows toward center (upward / inward).
    idx_b = int(np.argmin(py_b))
    assert float(dy_b[idx_b]) > 0.5
    assert float(dx_b[idx_b] * px_b[idx_b] + dy_b[idx_b] * py_b[idx_b]) < 0.0

    # Normal outward growth points away from center.
    idx_n = int(np.argmin(py_n))
    assert float(dx_n[idx_n] * px_n[idx_n] + dy_n[idx_n] * py_n[idx_n]) > 0.0


def test_normalize_accepts_normal_gravity() -> None:
    tpl = normalize_renderer_template(
        {
            "style": "orbit-spikes",
            "layers": [{"gravity": "normal", "barWidth": 5, "thickness": 30}],
        }
    )
    assert tpl["layers"][0]["gravity"] == "normal"


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
    assert layer["barCount"] == 128
    assert layer["solidBand"] is True
    assert layer["peakCapsEnabled"] is True
    assert layer["peakCapGap"] == 24.0
    assert layer["peakCapThickness"] == 1.0
    assert layer["peakCapDecay"] == 0.7


def test_bar_count_clamp_and_fft_resample() -> None:
    assert clamp_spectrum_bar_count(None) == 64
    assert clamp_spectrum_bar_count(2) == 16
    assert clamp_spectrum_bar_count(300) == 128
    src = np.linspace(0.0, 1.0, 64, dtype=np.float32)
    out = resample_fft_bins(src, 24)
    assert out.shape == (24,)
    assert float(out[0]) == 0.0
    assert float(out[-1]) == 1.0
