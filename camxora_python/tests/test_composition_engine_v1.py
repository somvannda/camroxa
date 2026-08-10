"""Engine-true P0–P6 composition tests (hard cut)."""

from __future__ import annotations

import pytest

from visualizer_studio.composition_effects.particles import build_particle_emitter, emitters_visibly_distinct
from visualizer_studio.presets import (
    ANIMATION_BEHAVIOR_COUNT,
    COLOR_PALETTE_COUNT,
    PARTICLE_TYPE_COUNT,
    SPECTRUM_MATERIAL_COUNT,
    SPECTRUM_SHAPE_COUNT,
)
from visualizer_studio.composition_renderer import CompositionContractError, document_to_renderer_dict
from visualizer_studio.scene import default_document, load_scene
from visualizer_studio.scene.compile import compile_scene


def _scene(
    *,
    shape: str,
    material: str,
    animation: str,
    palette: str = "cyberpunk",
    particle_type: str = "none",
    particle_behavior: str = "none",
    logo_animation: str = "none",
) -> dict:
    doc = default_document()
    doc["composition"]["colorPalette"] = palette
    doc["composition"]["spectrum"] = {
        "shape": shape,
        "material": material,
        "animation": animation,
    }
    doc["composition"]["particles"] = {"type": particle_type, "behavior": particle_behavior}
    doc["composition"]["logo"]["animation"] = logo_animation
    return doc


def test_catalog_counts() -> None:
    assert SPECTRUM_SHAPE_COUNT == 15
    assert SPECTRUM_MATERIAL_COUNT == 20
    assert ANIMATION_BEHAVIOR_COUNT == 12
    assert PARTICLE_TYPE_COUNT == 20
    assert COLOR_PALETTE_COUNT == 20


def test_fail_closed_without_composition() -> None:
    with pytest.raises(CompositionContractError):
        load_scene({"style": "orbit-spikes", "layers": []})
    with pytest.raises(CompositionContractError):
        document_to_renderer_dict({"particlesSettings": {"variant": "dust"}})


def test_neon_circle_pulse_compiles() -> None:
    compiled = compile_scene(_scene(shape="circle", material="neon", animation="pulse"))
    assert compiled.spectrum_shape == "circle"
    assert compiled.spectrum_material == "neon"
    assert compiled.spectrum_animation == "pulse"
    assert compiled.spectrum_layers[0]["pathMode"] == "circle"
    assert float(compiled.spectrum_layers[0]["glow"]) > 0.0
    assert compiled.to_renderer_dict().get("style") == "orbit-spikes"


def test_glass_hexagon_bounce() -> None:
    compiled = compile_scene(_scene(shape="hexagon", material="glass", animation="bounce"))
    assert compiled.spectrum_shape == "hexagon"
    assert compiled.spectrum_layers[0]["pathMode"] == "hexagon"
    assert compiled.spectrum_layers[0]["fillCircle"] is True


def test_fire_bars_flash() -> None:
    compiled = compile_scene(_scene(shape="bars", material="fire", animation="flash"))
    assert compiled.spectrum_shape == "bars"
    assert compiled.spectrum_animation == "flash"
    assert compiled.spectrum_layers[0]["blend_mode"] == "add"


def test_plasma_spiral_breathing() -> None:
    compiled = compile_scene(_scene(shape="spiral", material="plasma", animation="breathing"))
    assert compiled.spectrum_shape == "spiral"
    assert compiled.spectrum_layers[0]["pathMode"] == "spiral"
    assert compiled.spectrum_material == "plasma"


def test_material_does_not_change_shape() -> None:
    doc = _scene(shape="hexagon", material="neon", animation="pulse")
    a = compile_scene(doc)
    doc["composition"]["spectrum"]["material"] = "glass"
    b = compile_scene(doc)
    assert a.spectrum_shape == b.spectrum_shape == "hexagon"
    assert a.spectrum_layers[0]["pathMode"] == b.spectrum_layers[0]["pathMode"]
    assert a.spectrum_layers[0]["glow"] != b.spectrum_layers[0]["glow"]


def test_same_behavior_on_spectrum_and_logo() -> None:
    doc = _scene(
        shape="circle",
        material="neon",
        animation="pulse",
        logo_animation="pulse",
    )
    compiled = compile_scene(doc)
    assert compiled.spectrum_animation == "pulse"
    assert compiled.logo["animation"] == "pulse"
    assert compiled.logo["motion"]["scale"] != 0.0


def test_rain_vs_snow_distinct_under_same_behavior() -> None:
    rain = build_particle_emitter("rain", "pulse")
    snow = build_particle_emitter("snow", "pulse")
    assert rain is not None and snow is not None
    assert rain["typeId"] == "rain"
    assert snow["typeId"] == "snow"
    assert rain["behaviorId"] == snow["behaviorId"] == "pulse"
    assert emitters_visibly_distinct(rain, snow)


def test_particle_type_does_not_clear_behavior() -> None:
    doc = _scene(
        shape="circle",
        material="neon",
        animation="none",
        particle_type="dust",
        particle_behavior="wave",
    )
    a = compile_scene(doc)
    doc["composition"]["particles"]["type"] = "electric"
    b = compile_scene(doc)
    assert a.particles is not None and b.particles is not None
    assert a.particles["behaviorId"] == b.particles["behaviorId"] == "wave"
    assert a.particles["typeId"] == "dust"
    assert b.particles["typeId"] == "electric"


def test_renderer_dict_keeps_composition() -> None:
    payload = document_to_renderer_dict(_scene(shape="circle", material="neon", animation="pulse"))
    assert payload["composition"]["spectrum"]["shape"] == "circle"
    assert payload["engine"]["compiled"] is True
    assert payload["layers"][0]["shapeId"] == "circle"
