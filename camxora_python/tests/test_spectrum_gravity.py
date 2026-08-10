"""Tests for spectrum bar-growth directions including radial spikes."""

from __future__ import annotations

import numpy as np

from features.video.widgets.spectrum_layer_editor import GRAVITY_OPTIONS
from visualizer_video._spectrum_fast import (
    clamp_spectrum_bar_count,
    generate_points_curved,
    generate_points_linear,
    generate_spectrum_layer_geometry,
    is_radial_spectrum_gravity,
    normalize_spectrum_gravity,
    resample_fft_bins,
    resolve_curved_spectrum_basis,
    resolve_spectrum_growth_direction,
)
from visualizer_video.template_runtime import normalize_renderer_template


def test_gravity_options_include_radial_spikes() -> None:
    values = [value for value, _label in GRAVITY_OPTIONS]
    assert values == ["top", "bottom", "left", "right", "outward", "inward"]
    labels = [label for _value, label in GRAVITY_OPTIONS]
    assert labels[0] == "Top side"
    assert "All around — face out" in labels
    assert "normal" not in values


def test_normalize_maps_legacy_and_aliases() -> None:
    assert normalize_spectrum_gravity("normal") == "top"
    assert normalize_spectrum_gravity("BOTTOM") == "bottom"
    assert normalize_spectrum_gravity("outside") == "outward"
    assert normalize_spectrum_gravity("inside") == "inward"
    assert is_radial_spectrum_gravity("outward")
    assert is_radial_spectrum_gravity("in")
    assert not is_radial_spectrum_gravity("top")


def test_linear_directions_raise_as_labeled() -> None:
    _px, _py, dx, dy = generate_points_linear(8, 100.0, "top")
    assert np.allclose(dx, 0.0) and np.allclose(dy, 1.0)

    _px, _py, dx, dy = generate_points_linear(8, 100.0, "bottom")
    assert np.allclose(dx, 0.0) and np.allclose(dy, -1.0)

    _px, _py, dx, dy = generate_points_linear(8, 100.0, "left")
    assert np.allclose(dx, -1.0) and np.allclose(dy, 0.0)

    _px, _py, dx, dy = generate_points_linear(8, 100.0, "right")
    assert np.allclose(dx, 1.0) and np.allclose(dy, 0.0)


def test_curved_side_bars_raise_facing_out() -> None:
    """Top/Bottom/Left/Right place the arc; each bar raises radially out (its face)."""
    for gravity in ("top", "bottom", "left", "right"):
        start, gdx, gdy = resolve_curved_spectrum_basis(gravity)
        px, py, dx, dy = generate_points_curved(
            32, 100.0, False, start, gdx, gdy, gravity=gravity
        )
        radii = np.sqrt(px * px + py * py)
        assert np.allclose(radii, 100.0, atol=1e-3)
        assert np.allclose(dx, px / 100.0, atol=1e-4)
        assert np.allclose(dy, py / 100.0, atol=1e-4)


def test_legacy_uniform_growth_without_gravity_arg() -> None:
    """Callers that omit gravity still get uniform growth_dx/growth_dy."""
    start, gdx, gdy = resolve_curved_spectrum_basis("top")
    _px, _py, dx, dy = generate_points_curved(16, 100.0, True, start, 0.0, 1.0)
    assert np.allclose(dx, 0.0)
    assert np.allclose(dy, 1.0)


def test_radial_outward_spikes_match_ring_normals() -> None:
    start, gdx, gdy = resolve_curved_spectrum_basis("outward")
    assert (gdx, gdy) == (0.0, 0.0)
    px, py, dx, dy = generate_points_curved(32, 100.0, True, start, gdx, gdy, gravity="outward")
    radii = np.sqrt(px * px + py * py)
    assert np.allclose(radii, 100.0, atol=1e-3)
    assert np.allclose(dx, px / 100.0, atol=1e-4)
    assert np.allclose(dy, py / 100.0, atol=1e-4)


def test_radial_inward_spikes_point_to_center() -> None:
    start, gdx, gdy = resolve_curved_spectrum_basis("inward")
    px, py, dx, dy = generate_points_curved(24, 80.0, True, start, gdx, gdy, gravity="inward")
    assert np.allclose(dx, -px / 80.0, atol=1e-4)
    assert np.allclose(dy, -py / 80.0, atol=1e-4)


def test_geometry_helper_radial_outward() -> None:
    px, py, dx, dy, _length = generate_spectrum_layer_geometry(
        20,
        curved=True,
        mirrored=True,
        gravity="outward",
        path_mode="circle",
        radius=50.0,
        frame_w=1920,
        frame_h=1080,
    )
    assert px.shape == (20,)
    assert float(np.min(np.sqrt(dx * dx + dy * dy))) > 0.99


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


def test_normalize_accepts_radial_gravity() -> None:
    tpl = normalize_renderer_template(
        {
            "style": "orbit-spikes",
            "layers": [{"gravity": "outward", "barWidth": 5, "thickness": 30}],
        }
    )
    assert tpl["layers"][0]["gravity"] == "outward"
    tpl2 = normalize_renderer_template(
        {
            "style": "orbit-spikes",
            "layers": [{"gravity": "inside", "barWidth": 5, "thickness": 30}],
        }
    )
    assert tpl2["layers"][0]["gravity"] == "inward"


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


def test_raise_angle_overrides_uniform_direction() -> None:
    from visualizer_video._spectrum_fast import (
        apply_raise_angle_override,
        normalize_raise_angle_deg,
        raise_angle_direction,
    )

    assert normalize_raise_angle_deg(None) is None
    assert normalize_raise_angle_deg("auto") is None
    assert abs(float(normalize_raise_angle_deg(450.0)) - 90.0) < 1e-6

    right = raise_angle_direction(0.0)
    assert right is not None
    assert abs(right[0] - 1.0) < 1e-6
    assert abs(right[1]) < 1e-6

    up = raise_angle_direction(90.0)
    assert up is not None
    assert abs(up[0]) < 1e-6
    assert abs(up[1] - 1.0) < 1e-6

    from visualizer_video._spectrum_fast import apply_bar_height_overrides, scroll_spectrum_heights

    base = np.linspace(0.1, 1.0, 16, dtype=np.float32)
    scrolled = scroll_spectrum_heights(base, 0.25)
    assert scrolled.shape == base.shape
    assert float(scrolled[0]) != float(base[0])
    scaled = apply_bar_height_overrides(base, {"0": 2.0, "3": 0.5})
    assert abs(float(scaled[0]) - float(base[0]) * 2.0) < 1e-5
    assert abs(float(scaled[3]) - float(base[3]) * 0.5) < 1e-5

    px, py, dx, dy, _total = generate_spectrum_layer_geometry(
        32,
        curved=True,
        mirrored=True,
        gravity="outward",
        path_mode="diamond",
        radius=120.0,
        raise_angle_deg=0.0,
    )
    assert len(dx) == 32
    assert np.allclose(dx, 1.0, atol=1e-5)
    assert np.allclose(dy, 0.0, atol=1e-5)

    _px2, _py2, dx2, dy2, _t2 = generate_spectrum_layer_geometry(
        32,
        curved=True,
        mirrored=True,
        gravity="outward",
        path_mode="diamond",
        radius=120.0,
        raise_angle_deg=90.0,
    )
    assert np.allclose(dx2, 0.0, atol=1e-5)
    assert np.allclose(dy2, 1.0, atol=1e-5)

    odx = np.ones(8, dtype=np.float32)
    ody = np.zeros(8, dtype=np.float32)
    ndx, ndy = apply_raise_angle_override(odx, ody, 180.0)
    assert np.allclose(ndx, -1.0, atol=1e-5)
    assert np.allclose(ndy, 0.0, atol=1e-5)
