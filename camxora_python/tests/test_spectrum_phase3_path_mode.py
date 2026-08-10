"""Phase 3: spectrum pathMode circle|rect + LogoBounds DTO."""

from __future__ import annotations

import numpy as np

from features.video.lib.logo_spectrum_bindings import LogoBounds, build_logo_bounds, normalize_logo_shape
from visualizer_video._spectrum_fast import (
    generate_points_rect,
    generate_spectrum_layer_geometry,
    normalize_spectrum_path_mode,
    resolve_spectrum_path_mode,
)
from visualizer_video.template_runtime import default_renderer_template, normalize_renderer_template


def test_normalize_path_mode_aliases() -> None:
    assert normalize_spectrum_path_mode("AUTO") == "auto"
    assert normalize_spectrum_path_mode("rectangle") == "rect"
    assert normalize_spectrum_path_mode("square") == "rect"
    assert normalize_spectrum_path_mode("circle") == "circle"
    assert normalize_spectrum_path_mode("nope") == "auto"


def test_auto_path_uses_rect_when_attached_square() -> None:
    assert (
        resolve_spectrum_path_mode(
            "auto",
            curved=True,
            attached_to_logo=True,
            logo_shape="square",
        )
        == "rect"
    )
    assert (
        resolve_spectrum_path_mode(
            "auto",
            curved=True,
            attached_to_logo=True,
            logo_shape="circle",
        )
        == "circle"
    )
    assert (
        resolve_spectrum_path_mode(
            "auto",
            curved=False,
            attached_to_logo=True,
            logo_shape="square",
        )
        == "linear"
    )


def test_logo_bounds_dto() -> None:
    bounds = build_logo_bounds(
        cx=100.0,
        cy=200.0,
        logo_half_size=80.0,
        circle_mask=False,
        visible_radius_ratio=0.9,
        gap_px=12.0,
        attached=True,
    )
    assert isinstance(bounds, LogoBounds)
    assert bounds.shape == "square"
    assert normalize_logo_shape(circle_mask=True) == "circle"
    half_w, half_h = bounds.outer_half_extents()
    assert abs(half_w - (80.0 * 0.9 + 12.0)) < 1e-6
    assert abs(half_h - half_w) < 1e-6


def test_rect_semi_top_edge_outward() -> None:
    px, py, dx, dy = generate_points_rect(32, 50.0, 40.0, False, "top")
    assert px.shape == (32,)
    assert float(np.max(py)) == 40.0
    assert float(np.min(py)) == 40.0
    assert float(np.min(dx)) == 0.0 and float(np.max(dx)) == 0.0
    assert float(np.min(dy)) == 1.0 and float(np.max(dy)) == 1.0
    assert float(np.min(px)) >= -50.0 - 1e-3
    assert float(np.max(px)) <= 50.0 + 1e-3


def test_rect_full_perimeter_covers_all_sides() -> None:
    px, py, dx, dy = generate_points_rect(64, 30.0, 20.0, True, "top")
    assert px.shape == (64,)
    # Touch near each side
    assert float(np.max(py)) >= 19.5
    assert float(np.min(py)) <= -19.5
    assert float(np.max(px)) >= 29.5
    assert float(np.min(px)) <= -29.5
    # Outward normals only
    assert float(np.max(np.abs(dx))) <= 1.0 + 1e-6
    assert float(np.max(np.abs(dy))) <= 1.0 + 1e-6


def test_generate_geometry_auto_rect_path_length() -> None:
    px, py, dx, dy, length = generate_spectrum_layer_geometry(
        48,
        curved=True,
        mirrored=True,
        gravity="top",
        path_mode="auto",
        radius=40.0,
        half_w=40.0,
        half_h=40.0,
        attached_to_logo=True,
        logo_shape="square",
        frame_w=1920,
        frame_h=1080,
    )
    assert px.shape == (48,)
    assert abs(length - (2.0 * (2.0 * 40.0 + 2.0 * 40.0))) < 1e-3
    # Not a pure circle sample (corners land on rect edges)
    radii = np.sqrt(px * px + py * py)
    assert float(np.max(radii) - np.min(radii)) > 1.0


def test_template_normalizes_path_mode() -> None:
    tpl = default_renderer_template()
    tpl["layers"][0]["pathMode"] = "rectangle"
    out = normalize_renderer_template(tpl)
    assert out["layers"][0]["pathMode"] == "rect"
    tpl2 = default_renderer_template()
    out2 = normalize_renderer_template(tpl2)
    assert out2["layers"][0]["pathMode"] == "auto"
