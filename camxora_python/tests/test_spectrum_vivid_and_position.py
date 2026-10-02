"""Tests for spectrum/logo center decoupling and vivid style recipes."""

from __future__ import annotations

from features.video.lib.logo_spectrum_bindings import resolve_spectrum_logo_centers
from features.video.lib.spectrum_style_registry import (
    STACKED_LAYER_PRESETS,
    STYLE_PRESET_PATCHES,
    build_spectrum_preset_template,
)


def _fake_anchor(anchor: str, ox: float, oy: float, w: int, h: int) -> tuple[float, float]:
    cx = float(w) * 0.5
    cy = float(h) * 0.5
    if "left" in anchor:
        cx = 0.0
    elif "right" in anchor:
        cx = float(w)
    if "top" in anchor:
        cy = float(h)
    elif "bottom" in anchor:
        cy = 0.0
    return (cx + ox, cy - oy)


def test_detached_spectrum_moves_without_logo() -> None:
    spectrum, logo = resolve_spectrum_logo_centers(
        _fake_anchor,
        w=1000,
        h=800,
        sf=1.0,
        position={"anchor": "center", "x": 120, "y": -40},
        spectrum_attach_to_logo=False,
    )
    assert spectrum == (620.0, 440.0)
    assert logo == (500.0, 400.0)


def test_detached_logo_can_move_freely() -> None:
    spectrum, logo = resolve_spectrum_logo_centers(
        _fake_anchor,
        w=1000,
        h=800,
        sf=1.0,
        position={"anchor": "center", "x": 120, "y": -40},
        spectrum_attach_to_logo=False,
        logo_position={"anchor": "center", "x": -60, "y": 30},
    )
    assert spectrum == (620.0, 440.0)
    assert logo == (440.0, 370.0)


def test_attached_spectrum_and_logo_share_center() -> None:
    spectrum, logo = resolve_spectrum_logo_centers(
        _fake_anchor,
        w=1000,
        h=800,
        sf=1.0,
        position={"anchor": "center", "x": 80, "y": 20},
        spectrum_attach_to_logo=True,
    )
    assert spectrum == logo
    assert spectrum == (580.0, 380.0)


def test_builtin_style_presets_avoid_white_and_extreme_glow() -> None:
    for key, patch in STYLE_PRESET_PATCHES.items():
        colors = list((patch.get("color") or {}).get("gradientColors") or [])
        assert colors, key
        assert "#ffffff" not in {str(c).lower() for c in colors}, key
        # Bright catalog: average channel should stay well above dark-navy recipes.
        for hex_color in colors:
            raw = str(hex_color).lstrip("#")
            r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
            assert (r + g + b) / 3.0 >= 110.0, f"{key}:{hex_color}"
        assert float(patch.get("glow", 0)) <= 40.0, key
        assert float(patch.get("blur", 0)) <= 12.0, key
        assert str(patch.get("blend_mode", "normal")).lower() == "normal", key


def test_stacked_presets_use_normal_blend_and_vivid_stops() -> None:
    for key, recipe in STACKED_LAYER_PRESETS.items():
        for layer in recipe["layers"]:
            colors = list((layer.get("color") or {}).get("gradientColors") or [])
            assert "#ffffff" not in {str(c).lower() for c in colors}, f"{key}:{layer.get('name')}"
            assert str(layer.get("blend_mode", "normal")).lower() == "normal", key
            assert float(layer.get("glow", 0)) <= 40.0, key


def test_build_orbit_spikes_applies_vivid_recipe() -> None:
    patched = build_spectrum_preset_template({}, "orbit-spikes")
    colors = patched["layers"][0]["color"]["gradientColors"]
    assert colors[0].lower() != "#ffffff"
    assert "#ff00ff" in {c.lower() for c in colors} or "#00ffff" in {c.lower() for c in colors}


def test_gradient_dropdown_palettes_are_bright() -> None:
    from features.video.lib.spectrum_color_engine import (
        SPECTRUM_GRADIENT_PRESET_OPTIONS,
        _VIDEO_SPECTRUM_PALETTE_PRESETS,
    )

    assert len(SPECTRUM_GRADIENT_PRESET_OPTIONS) >= 30
    labels = {label for _value, label in SPECTRUM_GRADIENT_PRESET_OPTIONS}
    assert "Cyberpunk" in labels
    assert "Neon Candy" in labels
    # Video bright presets stay vivid for stage readability.
    for value, label in _VIDEO_SPECTRUM_PALETTE_PRESETS:
        assert "Night" not in label and "Dark" not in label and "Abyss" not in label
        for hex_color in value.split(","):
            raw = hex_color.strip().lstrip("#")
            r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
            assert (r + g + b) / 3.0 >= 110.0, f"{label}:{hex_color}"


def test_style_preset_restores_zero_opacity() -> None:
    from features.video.lib.spectrum_style_registry import heal_spectrum_layer_visibility

    patched = build_spectrum_preset_template(
        {"layers": [{"opacity": 0.0, "thickness": 40, "color": {"mode": "solid", "solidColor": "#ffffff"}}]},
        "magma-ridge",
    )
    assert float(patched["layers"][0]["opacity"]) >= 0.05
    healed = heal_spectrum_layer_visibility([{"opacity": 0.0}, {"opacity": 0.0}])
    assert all(float(layer["opacity"]) == 1.0 for layer in healed)
