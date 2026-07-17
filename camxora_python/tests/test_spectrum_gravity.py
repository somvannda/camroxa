"""Tests for spectrum gravity modes including Normal (straight rising)."""

from __future__ import annotations

import numpy as np

from features.video.widgets.spectrum_layer_editor import GRAVITY_OPTIONS
from visualizer._spectrum_fast import generate_points_linear
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


def test_normalize_accepts_normal_gravity() -> None:
    tpl = normalize_renderer_template(
        {
            "style": "orbit-spikes",
            "layers": [{"gravity": "normal", "barWidth": 5, "thickness": 30}],
        }
    )
    assert tpl["layers"][0]["gravity"] == "normal"
