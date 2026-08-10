"""Prism Core Glow — Studio-only Trap Nation-style multi-layer spectrum look."""

from __future__ import annotations

from features.studio.lib.scene_document import apply_axis_patch, inspector_bind_state, normalize_studio_document
from features.studio.lib.spectrum_looks import (
    normalize_spectrum_look_id,
    prism_core_glow_layers,
    spectrum_look_axis_patch,
)
from visualizer_studio.composition_renderer import document_to_renderer_dict


def test_normalize_prism_core_glow_aliases() -> None:
    assert normalize_spectrum_look_id("prism-core-glow") == "prism-core-glow"
    assert normalize_spectrum_look_id("trap-nation") == "prism-core-glow"
    assert normalize_spectrum_look_id("none") is None


def test_prism_core_glow_layers_are_three_stacked_rings() -> None:
    layers = prism_core_glow_layers()
    assert len(layers) == 3
    assert layers[0]["name"] == "Soft Aura"
    assert layers[1]["name"] == "Rainbow Body"
    assert layers[2]["name"] == "White Core"
    assert layers[2]["color"]["mode"] == "solid"
    assert layers[0]["color"]["gradientDirection"] == "circular"
    assert float(layers[0]["blur"]) > float(layers[1]["blur"]) >= float(layers[2]["blur"] or 0.0)


def test_spectrum_look_axis_patch_seeds_studio_document() -> None:
    doc = normalize_studio_document({})
    patched = apply_axis_patch(doc, spectrum_look_axis_patch("prism-core-glow"))
    spec = patched["composition"]["spectrum"]
    assert spec["look"] == "prism-core-glow"
    assert spec["shape"] == "circle"
    assert spec["material"] == "plasma"
    assert spec["colorPalette"] == "rainbow"
    assert len(spec["layers"]) == 3
    state = inspector_bind_state(patched)
    assert state["compositionSpectrumLook"] == "prism-core-glow"
    assert len(state["compositionSpectrumLayers"]) == 3


def test_prism_core_glow_compile_preserves_white_core_and_circular_rainbow() -> None:
    doc = apply_axis_patch(normalize_studio_document({}), spectrum_look_axis_patch("prism-core-glow"))
    doc["assets"]["logo"] = None
    rendered = document_to_renderer_dict(doc)
    assert rendered.get("style") == "plasma-bloom"
    layers = rendered.get("layers") or []
    assert len(layers) >= 3
    whites = [
        layer
        for layer in layers
        if isinstance(layer, dict)
        and isinstance(layer.get("color"), dict)
        and str(layer["color"].get("solidColor") or "").lower() in ("#ffffff", "#fff")
        and str(layer["color"].get("mode") or "") == "solid"
    ]
    assert whites, "expected a locked solid white core layer"
    rainbows = [
        layer
        for layer in layers
        if isinstance(layer, dict)
        and isinstance(layer.get("color"), dict)
        and str(layer["color"].get("gradientDirection") or "") == "circular"
    ]
    assert rainbows, "expected circular rainbow glow layers"
    assert any(float(layer.get("blur") or 0.0) >= 4.0 for layer in layers if isinstance(layer, dict))
