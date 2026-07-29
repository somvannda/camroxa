"""Tests for spectrum layer color engine."""

from __future__ import annotations

from features.video.lib.spectrum_color_engine import (
    apply_spectrum_layer_color_patch,
    extract_spectrum_layer_color_model,
    normalize_spectrum_gradient_colors,
)


def test_normalize_spectrum_gradient_colors_requires_two_stops() -> None:
    colors = normalize_spectrum_gradient_colors(["#ff0000"], "#00ff00")
    assert len(colors) == 2
    assert colors[0] == "#ff0000"


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
