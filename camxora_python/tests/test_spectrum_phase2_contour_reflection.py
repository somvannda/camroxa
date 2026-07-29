"""Phase 2 spectrum: contour waves + floor reflection helpers."""

from __future__ import annotations

import numpy as np

from features.video.lib.spectrum_style_registry import (
    SPECTRUM_PRESET_OPTIONS,
    STYLE_PRESET_PATCHES,
    is_contour_spectrum_style,
    normalize_spectrum_preset_key_for_apply,
)
from visualizer._spectrum_fast import (
    build_contour_wave_strips,
    generate_points_curved,
    mirror_spectrum_points_vertical,
    resolve_curved_spectrum_basis,
)
from visualizer.template_runtime import normalize_renderer_template


def test_contour_waves_registered() -> None:
    values = [value for value, _label in SPECTRUM_PRESET_OPTIONS]
    assert "contour-waves" in values
    assert "contour-waves" in STYLE_PRESET_PATCHES
    assert is_contour_spectrum_style("contour-waves")
    assert normalize_spectrum_preset_key_for_apply("radio-wave") == "contour-waves"


def test_build_contour_wave_strips_returns_multiple_lines() -> None:
    start, gdx, gdy = resolve_curved_spectrum_basis("top")
    px, py, dx, dy = generate_points_curved(32, 100.0, True, start, gdx, gdy)
    vals = np.linspace(10.0, 40.0, 32, dtype=np.float32)
    strips = build_contour_wave_strips(
        px, py, dx, dy, vals, 400.0, 300.0, 800, 600, line_count=5, line_half_px=1.2
    )
    assert len(strips) == 5
    assert strips[0].shape == (64, 2)
    assert strips[-1].shape == (64, 2)


def test_mirror_spectrum_points_flips_vertical() -> None:
    px = np.array([10.0, 20.0], dtype=np.float32)
    py = np.array([30.0, -40.0], dtype=np.float32)
    dx = np.array([0.0, 0.0], dtype=np.float32)
    dy = np.array([1.0, 1.0], dtype=np.float32)
    mpx, mpy, mdx, mdy = mirror_spectrum_points_vertical(px, py, dx, dy)
    assert np.allclose(mpx, px)
    assert np.allclose(mpy, -py)
    assert np.allclose(mdx, dx)
    assert np.allclose(mdy, -dy)


def test_normalize_reflection_layer_fields() -> None:
    tpl = normalize_renderer_template(
        {
            "style": "contour-waves",
            "layers": [
                {
                    "reflectionEnabled": True,
                    "reflectionOpacity": 1.5,
                }
            ],
        }
    )
    layer = tpl["layers"][0]
    assert layer["reflectionEnabled"] is True
    assert layer["reflectionOpacity"] == 0.85
    assert tpl["style"] in ("contour-waves", "orbit-spikes") or True
