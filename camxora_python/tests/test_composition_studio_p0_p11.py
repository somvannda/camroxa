"""Composition Studio P0–P11 engine + compile golden checks."""

from __future__ import annotations

import pytest

from visualizer.composition_effects.audio_mapping import (
    apply_mapping_levels,
    normalize_audio_mapping,
    resolve_bus_levels,
)
from visualizer.presets import (
    ANIMATION_BEHAVIOR_COUNT,
    ATMOSPHERE_COUNT,
    AUDIO_BUS_COUNT,
    BACKGROUND_MOTION_COUNT,
    CAMERA_BEHAVIOR_COUNT,
    COLOR_PALETTE_COUNT,
    LIGHTING_EFFECT_COUNT,
    PARTICLE_TYPE_COUNT,
    POST_EFFECT_COUNT,
    SPECTRUM_MATERIAL_COUNT,
    SPECTRUM_SHAPE_COUNT,
)
from visualizer.scene import default_document, load_scene
from visualizer.scene.compile import compile_scene
from visualizer.template_runtime import normalize_renderer_template


def test_p0_p11_catalog_counts() -> None:
    assert SPECTRUM_SHAPE_COUNT == 15
    assert SPECTRUM_MATERIAL_COUNT == 20
    assert ANIMATION_BEHAVIOR_COUNT == 12
    assert PARTICLE_TYPE_COUNT == 20
    assert COLOR_PALETTE_COUNT == 20
    assert LIGHTING_EFFECT_COUNT == 15
    assert CAMERA_BEHAVIOR_COUNT == 15
    assert ATMOSPHERE_COUNT == 15
    assert BACKGROUND_MOTION_COUNT == 10
    assert POST_EFFECT_COUNT == 20
    assert AUDIO_BUS_COUNT == 8


def _full_scene() -> dict:
    doc = default_document()
    doc["composition"].update(
        {
            "colorPalette": "cyberpunk",
            "background": {"image": None, "motion": "ken_burns", "atmosphere": "fog"},
            "spectrum": {"shape": "circle", "material": "neon", "animation": "pulse"},
            "logo": {"enabled": True, "animation": "pulse"},
            "text": {"enabled": True},
            "overlay": {"enabled": True, "animation": "fade", "items": []},
            "particles": {"type": "sparkles", "behavior": "pulse"},
            "lighting": {"effect": "lightning", "trigger": "bass"},
            "camera": {"behavior": "shake"},
            "postProcessing": {"effects": ["bloom", "vignette", "film_grain"]},
            "audio": {
                "mapping": {
                    "lighting": "bass",
                    "particles": "kick",
                    "camera": "bass",
                    "logo": "vocals",
                }
            },
        }
    )
    return doc


def test_golden_full_composition_compiles() -> None:
    compiled = compile_scene(_full_scene(), time_sec=1.0, audio_level=0.8)
    assert compiled.spectrum_shape == "circle"
    assert compiled.lighting is not None
    assert compiled.lighting["effectId"] == "lightning"
    assert compiled.camera["behaviorId"] == "shake"
    assert compiled.atmosphere is not None
    assert compiled.atmosphere["atmosphereId"] == "fog"
    assert compiled.background["motion"] == "ken_burns"
    assert len(compiled.post["effects"]) == 3
    assert compiled.audio_mapping["mapping"]["logo"] == "vocals"
    rendered = compiled.to_renderer_dict()
    assert rendered["engine"]["compiled"] is True
    assert "style" not in rendered
    assert rendered["lightingSettings"]["effectId"] == "lightning"
    assert "bloom" in rendered["effects"]


def test_preview_normalize_keeps_engine_pass() -> None:
    rendered = compile_scene(_full_scene()).to_renderer_dict()
    normalized = normalize_renderer_template(rendered)
    assert normalized.get("schema") == "camxora.composition"
    assert isinstance(normalized.get("composition"), dict)
    assert normalized.get("engine", {}).get("compiled") is True
    assert normalized.get("lightingSettings", {}).get("effectId") == "lightning"
    assert "bloom" in (normalized.get("effects") or {})


def test_audio_mapping_heuristics() -> None:
    levels = resolve_bus_levels(
        bass=0.9,
        treble=0.2,
        kick=0.8,
        overall=0.7,
        mid=0.55,
        presence=0.6,
        transient_mid=0.4,
    )
    assert levels["vocals"] == pytest.approx(0.6)
    assert levels["melody"] == pytest.approx(0.55)
    assert levels["snare"] == pytest.approx(0.4)
    mapping = normalize_audio_mapping(
        {"lighting": "bass", "particles": "kick", "camera": "bass", "logo": "vocals"}
    )
    mapped = apply_mapping_levels(mapping, levels)
    assert mapped["lighting"] == pytest.approx(0.9)
    assert mapped["logo"] == pytest.approx(0.6)


def test_orthogonal_atmosphere_vs_particles() -> None:
    doc = default_document()
    doc["composition"]["background"]["atmosphere"] = "rain"
    doc["composition"]["particles"]["type"] = "rain"
    compiled = compile_scene(doc)
    assert compiled.atmosphere["atmosphereId"] == "rain"
    assert compiled.particles is not None
    assert compiled.particles.get("typeId") == "rain"
    assert compiled.atmosphere["layer"] == "atmosphere"


def test_motion_independent_of_atmosphere() -> None:
    doc = default_document()
    doc["composition"]["background"] = {
        "image": None,
        "motion": "orbit",
        "atmosphere": "nebula",
    }
    a = compile_scene(doc)
    doc["composition"]["background"]["atmosphere"] = "void"
    b = compile_scene(doc)
    assert a.background["motion"] == b.background["motion"] == "orbit"
    assert a.atmosphere["atmosphereId"] == "nebula"
    assert b.atmosphere["atmosphereId"] == "void"


def test_fail_closed_still() -> None:
    with pytest.raises(Exception):
        load_scene({"style": "orbit-spikes"})
