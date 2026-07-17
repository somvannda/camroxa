"""Tests for particle color engine."""

from __future__ import annotations

from features.video.lib.particle_color_engine import (
    apply_particle_color_draft_patch,
    build_particle_rgba_rows,
    compute_particle_react_mix,
    extract_particle_color_model,
    sample_palette_rgb,
)


def test_extract_particle_color_model_defaults_to_solid() -> None:
    model = extract_particle_color_model({"color": "#ff8800"})
    assert model["mode"] == "solid"
    assert model["solidColor"] == "#ff8800"


def test_apply_particle_color_draft_patch_keeps_palette_mode_on_preset_change() -> None:
    draft = {
        "particlesColor": "#ffffff",
        "particlesColorMode": "palette",
        "particlesPaletteColors": ["#ff4500", "#ff1493"],
        "particlesReactColor": "#fff4d6",
    }
    next_draft = apply_particle_color_draft_patch(
        draft,
        {"paletteColors": ["#00ffff", "#ffffff"]},
    )
    assert next_draft["particlesColorMode"] == "palette"
    assert next_draft["particlesPaletteColors"] == ["#00ffff", "#ffffff"]
    assert next_draft["particlesReactColor"] == "#fff4d6"


def test_apply_particle_color_draft_patch_updates_react_color_in_palette_mode() -> None:
    draft = {
        "particlesColor": "#ffffff",
        "particlesColorMode": "palette",
        "particlesPaletteColors": ["#ff4500", "#ff1493"],
        "particlesReactColor": "#ffffff",
    }
    next_draft = apply_particle_color_draft_patch(draft, {"reactColor": "#ffe082"})
    assert next_draft["particlesColorMode"] == "palette"
    assert next_draft["particlesReactColor"] == "#ffe082"


def test_sample_palette_rgb_interpolates_stops() -> None:
    start = sample_palette_rgb(["#000000", "#ffffff"], 0.0)
    end = sample_palette_rgb(["#000000", "#ffffff"], 1.0)
    assert start == (0, 0, 0)
    assert end == (255, 255, 255)


def test_compute_particle_react_mix_matches_electron_curve() -> None:
    # Kick-heavy: trigger 0.6 → colorDrive ~1.0 → mix == strength
    assert compute_particle_react_mix(reactive_env=0.2, trigger_env=0.6, react_strength=0.65) == 0.65
    # Quiet: near-zero drive stays near zero
    quiet = compute_particle_react_mix(reactive_env=0.02, trigger_env=0.0, react_strength=1.0)
    assert quiet < 0.1


def test_build_particle_rgba_rows_applies_react_mix() -> None:
    import numpy as np

    rows = build_particle_rgba_rows(
        settings={
            "opacity": 1.0,
            "reactStrength": 1.0,
            "reactColor": "#ff0000",
            "color": "#0000ff",
        },
        particle_rgbs=np.array([[0, 0, 255]], dtype=np.float32),
        reactive_env=0.0,
        trigger_env=1.0,
    )
    assert rows.shape == (1, 4)
    assert rows[0, 0] > 0.9
    assert rows[0, 2] < 0.1


def test_build_particle_rgba_rows_uses_sustained_drive() -> None:
    import numpy as np

    quiet = build_particle_rgba_rows(
        settings={
            "opacity": 1.0,
            "reactStrength": 1.0,
            "reactColor": "#00ff00",
            "color": "#ff0000",
        },
        particle_rgbs=np.array([[255, 0, 0]], dtype=np.float32),
        reactive_env=0.0,
        trigger_env=0.0,
    )
    driven = build_particle_rgba_rows(
        settings={
            "opacity": 1.0,
            "reactStrength": 1.0,
            "reactColor": "#00ff00",
            "color": "#ff0000",
        },
        particle_rgbs=np.array([[255, 0, 0]], dtype=np.float32),
        reactive_env=0.45,
        trigger_env=0.1,
    )
    assert driven[0, 1] > quiet[0, 1]
    # Electron curve should produce a clearly visible green shift.
    assert driven[0, 1] > 0.35
