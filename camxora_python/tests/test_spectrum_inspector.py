"""Tests for spectrum inspector helpers and Camxora-native preset registry."""

from __future__ import annotations

from features.video.lib.spectrum_audio_dial import (
    FLYING_GLOW_WING_SPEED_DIAL_MAX,
    SPECTRUM_AUDIO_DIAL_MAX,
    from_spectrum_audio_dial,
    to_spectrum_audio_dial,
)
from features.video.lib.spectrum_style_registry import (
    SPECTRUM_PRESET_OPTIONS,
    build_spectrum_preset_template,
    build_stacked_spectrum_preset_template,
    build_unified_spectrum_preset_options,
    encode_pack_preset_key,
    normalize_spectrum_preset_key_for_apply,
)
from features.video.lib.video_template_draft import clone_layer_records, normalize_spectrum_preset_key
from visualizer_video.gpu_render import _resolve_export_spectrum_style


def test_spectrum_audio_dial_round_trip() -> None:
    dial = to_spectrum_audio_dial(5.5, 0, 10, SPECTRUM_AUDIO_DIAL_MAX)
    value = from_spectrum_audio_dial(dial, 0, 10, SPECTRUM_AUDIO_DIAL_MAX)
    assert dial == 11
    assert abs(value - 5.5) < 0.01


def test_flying_glow_wing_speed_dial_uses_extended_range() -> None:
    dial = to_spectrum_audio_dial(10, 0.5, 20, FLYING_GLOW_WING_SPEED_DIAL_MAX)
    assert dial == 49
    assert abs(from_spectrum_audio_dial(dial, 0.5, 20, FLYING_GLOW_WING_SPEED_DIAL_MAX) - 10) < 0.2


def test_normalize_spectrum_preset_aliases_to_camxora() -> None:
    assert normalize_spectrum_preset_key_for_apply("ignition-flare") == "ignition-flare"
    assert normalize_spectrum_preset_key_for_apply("orbit-spikes") == "orbit-spikes"
    assert normalize_spectrum_preset_key_for_apply("classic-vertical") == "orbit-spikes"
    assert normalize_spectrum_preset_key_for_apply("straight-bars") == "orbit-spikes"
    assert normalize_spectrum_preset_key_for_apply("neon-pulse") == "ignition-flare"
    assert normalize_spectrum_preset_key_for_apply("flying-glow") == "ignition-flare"
    assert normalize_spectrum_preset_key("soft-waveform") == "aurora-ribbon"
    assert normalize_spectrum_preset_key("mountain") == "magma-ridge"


def test_resolve_export_spectrum_style_maps_legacy_and_native() -> None:
    assert _resolve_export_spectrum_style("orbit-spikes") == "orbit-spikes"
    assert _resolve_export_spectrum_style("classic-vertical") == "orbit-spikes"
    assert _resolve_export_spectrum_style("neon-pulse") == "ignition-flare"
    assert _resolve_export_spectrum_style("flying-glow", {"fillCircle": True}) == "plasma-bloom"
    assert _resolve_export_spectrum_style("flying-glow", {"fillCircle": False}) == "magma-ridge"


def test_build_spectrum_preset_template_updates_style_and_layers() -> None:
    template = {
        "style": "orbit-spikes",
        "layers": [{"id": "layer-1", "name": "Old", "color": {"mode": "solid", "solidColor": "#111111"}}],
    }
    patched = build_spectrum_preset_template(template, "ignition-flare")
    assert patched["style"] == "ignition-flare"
    layers = clone_layer_records(patched.get("layers"))
    assert len(layers) == 1
    assert layers[0]["barWidth"] == 7.5
    assert layers[0]["thickness"] == 48.0
    # Styles start as straight bars; Curve 180 / Mirror 360 make the ring.
    assert layers[0]["curved"] is False
    assert layers[0]["mirrored"] is False


def test_build_spectrum_preset_template_replaces_mixed_geometry_stack() -> None:
    template = {
        "style": "orbit-spikes",
        "layers": [
            {"id": "ring", "name": "Ring", "curved": True, "mirrored": True, "barWidth": 4.0},
            {"id": "horizontal", "name": "Bars", "curved": False, "mirrored": False, "barWidth": 8.0},
        ],
    }
    patched = build_spectrum_preset_template(template, "ignition-flare")
    layers = clone_layer_records(patched.get("layers"))
    assert len(layers) == 1
    assert layers[0]["curved"] is False
    assert layers[0]["mirrored"] is False
    assert layers[0]["barWidth"] == 7.5


def test_build_spectrum_preset_template_can_patch_selected_layer_without_replace() -> None:
    template = {
        "style": "orbit-spikes",
        "layers": [
            {"id": "layer-1", "name": "Keep", "barWidth": 1.0, "curved": True},
            {"id": "layer-2", "name": "Target", "barWidth": 2.0, "curved": True},
        ],
    }
    patched = build_spectrum_preset_template(template, "signal-needles", layer_index=1, replace_stack=False)
    layers = clone_layer_records(patched.get("layers"))
    assert len(layers) == 2
    assert layers[0]["barWidth"] == 1.0
    assert layers[1]["barWidth"] == 1.6
    assert layers[1]["thickness"] == 44.0
    assert layers[1]["curved"] is False
    assert patched["style"] == "signal-needles"


def test_build_stacked_spectrum_preset_forces_ring_geometry() -> None:
    template = {
        "style": "orbit-spikes",
        "layers": [{"curved": False, "mirrored": False, "barWidth": 9.0}],
    }
    patched = build_stacked_spectrum_preset_template(template, "triple-halo-orbit")
    assert patched is not None
    assert patched["style"] == "ignition-flare"
    assert len(patched["layers"]) == 3
    for layer in patched["layers"]:
        assert layer["curved"] is True
        assert layer["mirrored"] is True


def test_legacy_stacked_alias_still_applies() -> None:
    template = {"style": "orbit-spikes", "layers": []}
    patched = build_stacked_spectrum_preset_template(template, "triple-neon-halo")
    assert patched is not None
    assert patched["style"] == "ignition-flare"
    assert len(patched["layers"]) == 3


def test_build_spectrum_preset_template_falls_back_to_orbit_spikes() -> None:
    template = {"style": "orbit-spikes", "layers": [{"barWidth": 9.0}]}
    patched = build_spectrum_preset_template(template, "unknown-style-key")
    assert patched["style"] == "orbit-spikes"
    layers = clone_layer_records(patched.get("layers"))
    assert layers[0]["barWidth"] == 5.0


def test_build_stacked_spectrum_preset_template() -> None:
    template = {"style": "orbit-spikes", "layers": []}
    patched = build_stacked_spectrum_preset_template(template, "triple-halo-orbit")
    assert patched is not None
    assert patched["style"] == "ignition-flare"
    assert len(patched["layers"]) == 3


def test_all_curated_presets_have_recipes() -> None:
    template = {"style": "orbit-spikes", "layers": []}
    for preset_key, _label in SPECTRUM_PRESET_OPTIONS:
        patched = build_spectrum_preset_template(template, preset_key)
        assert patched["style"] == preset_key
        assert isinstance(patched.get("layers"), list)
        assert len(patched["layers"]) >= 1


def test_build_unified_spectrum_preset_options_includes_installed_packs() -> None:
    catalog = [
        {
            "domain": "spectrum",
            "packId": "neon-pack",
            "version": "1.0.0",
            "name": "Neon Pack",
            "status": "ready",
        },
        {
            "domain": "background",
            "packId": "bg-pack",
            "version": "1.0.0",
            "name": "BG Pack",
            "status": "ready",
        },
    ]
    options = build_unified_spectrum_preset_options(catalog)
    assert options[: len(SPECTRUM_PRESET_OPTIONS)] == SPECTRUM_PRESET_OPTIONS
    assert encode_pack_preset_key("neon-pack", "1.0.0") in [value for value, _label in options]
    assert all("bg-pack" not in value for value, _label in options)
