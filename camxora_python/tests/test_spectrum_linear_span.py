"""Linear spectrum row span + flush preview-edge drag clamp."""

from __future__ import annotations

from visualizer._spectrum_fast import clamp_linear_span, generate_spectrum_layer_geometry
from visualizer.preview_widget import clamp_template_offset_to_preview
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def test_clamp_linear_span_bounds() -> None:
    assert clamp_linear_span(1.0) == 1.0
    assert clamp_linear_span(0.05) == 0.1
    assert clamp_linear_span(2.0) == 1.0
    assert clamp_linear_span(None) == 1.0


def test_linear_geometry_can_span_full_preview_width() -> None:
    _px, _py, _dx, _dy, length = generate_spectrum_layer_geometry(
        32,
        curved=False,
        mirrored=False,
        gravity="top",
        path_mode="auto",
        radius=40.0,
        frame_w=1000,
        frame_h=500,
        linear_span=1.0,
    )
    assert abs(length - 1000.0) < 1e-6


def test_linear_geometry_respects_partial_span() -> None:
    _px, _py, _dx, _dy, length = generate_spectrum_layer_geometry(
        32,
        curved=False,
        mirrored=False,
        gravity="top",
        path_mode="auto",
        radius=40.0,
        frame_w=1000,
        frame_h=500,
        linear_span=0.5,
    )
    assert abs(length - 500.0) < 1e-6


def test_normalize_keeps_linear_span() -> None:
    tpl = default_renderer_template()
    tpl["layers"][0]["linearSpan"] = 0.72
    out = normalize_renderer_template(tpl)
    assert abs(float(out["layers"][0]["linearSpan"]) - 0.72) < 1e-6


def test_clamp_allows_flush_bottom_edge() -> None:
    # OpenGL Y-up: bottom edge is cy=0. Center anchor with large negative offset.
    ox, oy = clamp_template_offset_to_preview(
        anchor="center",
        offset_x=0.0,
        offset_y=5000.0,  # pushes center toward bottom (cy = base_y - oy_px)
        w=800,
        h=450,
        sf=1.0,
        margin_frac=0.0,
    )
    # cy clamped to 0 => oy = base_y - 0 = 225
    assert abs(oy - 225.0) < 1e-6
    assert abs(ox) < 1e-6
