"""Tests for spectrum layer color engine."""

from __future__ import annotations

from features.video.lib.spectrum_color_engine import (
    apply_spectrum_layer_color_patch,
    build_spectrum_bar_quad_rgba,
    extract_spectrum_layer_color_model,
    normalize_spectrum_gradient_colors,
)


def test_normalize_spectrum_gradient_colors_requires_two_stops() -> None:
    colors = normalize_spectrum_gradient_colors(["#ff0000"], "#00ff00")
    assert len(colors) == 2
    assert colors[0] == "#ff0000"


def test_normalize_allows_up_to_twelve_gradient_stops() -> None:
    from features.video.lib.spectrum_color_engine import MAX_GRADIENT_COLOR_STOPS

    many = [f"#{i:02x}80ff" for i in range(16)]
    colors = normalize_spectrum_gradient_colors(many, "#ffffff")
    assert MAX_GRADIENT_COLOR_STOPS == 12
    assert len(colors) == 12


def test_vivid_palette_catalog_has_multi_stop_presets() -> None:
    from features.video.lib.spectrum_color_engine import (
        SPECTRUM_GRADIENT_PRESET_OPTIONS,
        spectrum_gradient_preset_colors,
    )

    assert len(SPECTRUM_GRADIENT_PRESET_OPTIONS) >= 30
    labels = [label for _value, label in SPECTRUM_GRADIENT_PRESET_OPTIONS]
    # Studio palettes are listed first, then Video bright presets.
    assert labels[0] == "Cyberpunk"
    assert "Rainbow" in labels
    assert "Neon Candy" in labels
    rainbow = next(v for v, label in SPECTRUM_GRADIENT_PRESET_OPTIONS if label == "Rainbow")
    assert len(spectrum_gradient_preset_colors(rainbow)) >= 6
    # Custom stop editing still allows up to the engine max.
    from features.video.lib.spectrum_color_engine import MAX_GRADIENT_COLOR_STOPS

    assert MAX_GRADIENT_COLOR_STOPS >= 8


def test_extract_spectrum_layer_color_model_reads_nested_color() -> None:
    layer = {
        "color": {
            "mode": "gradient",
            "solidColor": "#ffffff",
            "gradientDirection": "circular",
            "gradientColors": ["#111111", "#222222"],
        }
    }
    model = extract_spectrum_layer_color_model(layer, "#abcdef")
    assert model["mode"] == "gradient"
    assert model["gradientDirection"] == "circular"
    assert model["gradientColors"] == ["#111111", "#222222"]


def test_apply_spectrum_layer_color_patch_updates_nested_color() -> None:
    layer = {"name": "Ring", "color": {"mode": "solid", "solidColor": "#ffffff"}}
    patched = apply_spectrum_layer_color_patch(layer, {"solidColor": "#ff00ff"}, "#ffffff")
    assert patched["solidColor"] == "#ff00ff"
    assert patched["color"]["solidColor"] == "#ff00ff"


def test_build_spectrum_vertex_rgba_uses_all_gradient_stops() -> None:
    """Preview used to blend only first→last; middle stops must affect mid bars."""
    from features.video.lib.spectrum_color_engine import build_spectrum_vertex_rgba

    rgba = build_spectrum_vertex_rgba(
        mode="gradient",
        solid_color="#ffffff",
        gradient_colors=["#ff0000", "#00ff00", "#0000ff"],
        count=5,
        alpha=1.0,
    )
    assert rgba.shape == (5, 4)
    # First stop red, middle near green, last blue.
    assert float(rgba[0, 0]) > 0.9 and float(rgba[0, 1]) < 0.1
    assert float(rgba[2, 1]) > 0.9 and float(rgba[2, 0]) < 0.2
    assert float(rgba[4, 2]) > 0.9 and float(rgba[4, 0]) < 0.1
    # Old first→last-only path would make mid ≈ purple (r≈0.5, b≈0.5, g≈0).
    assert float(rgba[2, 1]) > float(rgba[2, 0])
    assert float(rgba[2, 1]) > float(rgba[2, 2])


def test_build_spectrum_vertex_rgba_keeps_stops_crystal_clear() -> None:
    """Stops stay readable — no neighbor wash that muddies dark palettes."""
    from features.video.lib.spectrum_color_engine import build_spectrum_vertex_rgba

    rgba = build_spectrum_vertex_rgba(
        mode="gradient",
        solid_color="#ffffff",
        gradient_colors=["#9f1239", "#1e3a8a", "#0f766e"],
        count=9,
        alpha=1.0,
    )
    # First stop stays deep red-dominant; last stays teal-dominant.
    assert float(rgba[0, 0]) > float(rgba[0, 2])
    assert float(rgba[8, 1]) > float(rgba[8, 0]) * 0.5
    # Mid stop near blue.
    assert float(rgba[4, 2]) > float(rgba[4, 0])


def test_build_spectrum_bar_quad_rgba_uses_vertical_gradient_for_top_to_bottom() -> None:
    rows = build_spectrum_bar_quad_rgba(
        mode="gradient",
        solid_color="#ffffff",
        gradient_colors=["#ff0000", "#0000ff"],
        count=2,
        alpha=0.75,
        gradient_direction="top-to-bottom",
    )
    assert rows.shape == (12, 4)
    # First bar base verts red.
    assert float(rows[0, 0]) > 0.9 and float(rows[0, 2]) < 0.1
    assert float(rows[1, 0]) > 0.9 and float(rows[1, 2]) < 0.1
    # First bar tip verts blue.
    assert float(rows[2, 2]) > 0.9 and float(rows[2, 0]) < 0.1
    assert float(rows[5, 2]) > 0.9 and float(rows[5, 0]) < 0.1
    assert float(rows[0, 3]) == 0.75


def test_radial_gradient_aliases_base_to_tip() -> None:
    rows = build_spectrum_bar_quad_rgba(
        mode="gradient",
        solid_color="#ffffff",
        gradient_colors=["#ff0000", "#0000ff"],
        count=1,
        alpha=1.0,
        gradient_direction="radial",
    )
    assert float(rows[0, 0]) > 0.9
    assert float(rows[2, 2]) > 0.9


def test_dampen_spectrum_glow_rgba_reduces_rgb() -> None:
    from features.video.lib.spectrum_color_engine import dampen_spectrum_glow_rgba
    import numpy as np

    src = np.array([[1.0, 0.5, 0.25, 0.8]], dtype=np.float32)
    out = dampen_spectrum_glow_rgba(src, strength=0.4)
    assert float(out[0, 0]) < float(src[0, 0])
    assert float(out[0, 1]) < float(src[0, 1])
    assert float(out[0, 3]) <= float(src[0, 3])


def test_solid_graph_strip_uses_spatial_melt_not_index_wrap() -> None:
    """Closed solid graph must not put first-stop against last-stop at the join."""
    import numpy as np
    from features.video.lib.spectrum_color_engine import (
        build_spectrum_solid_graph_strip_rgba,
        build_spectrum_vertex_rgba,
    )

    # Left and right tips at similar Y; left/right X map to opposite sides of LTR.
    # Index wrap would color tip 0 red and tip N-1 blue even when they meet.
    tip_xs = np.array([-0.9, -0.3, 0.3, 0.9, -0.9], dtype=np.float32)
    tip_ys = np.zeros(5, dtype=np.float32)
    strip = build_spectrum_solid_graph_strip_rgba(
        tip_xs_ndc=tip_xs,
        tip_ys_ndc=tip_ys,
        mode="gradient",
        solid_color="#ffffff",
        gradient_colors=["#ff0000", "#0000ff"],
        alpha=1.0,
        gradient_direction="left-to-right",
        close_loop=True,
    )
    assert strip.shape == (10, 4)
    # Closing sample matches first tip color (exact close_loop).
    assert np.allclose(strip[0], strip[8], atol=1e-5)
    assert np.allclose(strip[1], strip[9], atol=1e-5)
    # Spatial: leftmost tip stays red-dominant; rightmost tip blue-dominant.
    assert float(strip[0, 0]) > float(strip[0, 2])
    assert float(strip[6, 2]) > float(strip[6, 0])
    # Index path would force tip[-1] to last stop (blue) even when closed to tip[0].
    index_cols = build_spectrum_vertex_rgba(
        mode="gradient",
        solid_color="#ffffff",
        gradient_colors=["#ff0000", "#0000ff"],
        count=5,
        alpha=1.0,
    )
    assert float(index_cols[-1, 2]) > 0.9
    assert float(strip[8, 0]) > float(strip[8, 2])


def test_fill_fan_still_has_center_mid_stop() -> None:
    import numpy as np
    from features.video.lib.spectrum_color_engine import build_spectrum_fill_fan_rgba

    xs = np.array([-1.0, 0.0, 1.0], dtype=np.float32)
    ys = np.zeros(3, dtype=np.float32)
    fan = build_spectrum_fill_fan_rgba(
        xs_ndc=xs,
        ys_ndc=ys,
        mode="gradient",
        solid_color="#ffffff",
        gradient_colors=["#ff0000", "#00ff00", "#0000ff"],
        alpha=1.0,
        gradient_direction="left-to-right",
        close_loop=False,
    )
    assert fan.shape == (4, 4)
    # Center ≈ mid green stop.
    assert float(fan[0, 1]) > float(fan[0, 0])
    assert float(fan[0, 1]) > float(fan[0, 2])


def test_circle_form_from_layer_mapping() -> None:
    from features.video.widgets.spectrum_layer_editor import SpectrumLayerEditor

    assert SpectrumLayerEditor._circle_form_from_layer({"curved": False}) == "linear"
    assert SpectrumLayerEditor._circle_form_from_layer({"curved": True, "mirrored": False}) == "semi"
    assert SpectrumLayerEditor._circle_form_from_layer({"curved": True, "mirrored": True}) == "full"
