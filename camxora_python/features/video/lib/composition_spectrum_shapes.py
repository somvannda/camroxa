"""Composition Engine P3 — spectrum shape catalog (15 geometries).

``composition.spectrum.shape`` ids are geometry, not full look presets.
Applying a shape patches layer path/geometry only and preserves material /
animation / colors already on the template.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from features.video.lib.composition_axes import apply_spectrum_axes
from features.video.lib.composition_scene_contract import (
    NONE,
    ensure_composition_on_template,
    normalize_composition_scene,
)

# Canonical 12 + fill 3 (Ring, Starburst, Soft EQ) → 15
_SHAPE_ROWS: tuple[tuple[str, str], ...] = (
    ("circle", "Circle"),
    ("double_circle", "Double Circle"),
    ("wave", "Wave"),
    ("bars", "Bars"),
    ("hexagon", "Hexagon"),
    ("diamond", "Diamond"),
    ("triangle", "Triangle"),
    ("infinity", "Infinity"),
    ("heart", "Heart"),
    ("audio_ribbon", "Audio Ribbon"),
    ("spiral", "Spiral"),
    ("tunnel", "Tunnel"),
    ("ring", "Ring"),
    ("starburst", "Starburst"),
    ("soft_eq", "Soft EQ"),
)

SPECTRUM_SHAPE_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _SHAPE_ROWS
)
SPECTRUM_SHAPE_IDS: frozenset[str] = frozenset(item["id"] for item in SPECTRUM_SHAPE_CATALOG)
SPECTRUM_SHAPE_COUNT = len(SPECTRUM_SHAPE_CATALOG)
assert SPECTRUM_SHAPE_COUNT == 15, SPECTRUM_SHAPE_COUNT

_SHAPE_ALIASES: dict[str, str] = {
    "circle": "circle",
    "double circle": "double_circle",
    "double-circle": "double_circle",
    "double_circle": "double_circle",
    "wave": "wave",
    "bars": "bars",
    "bar": "bars",
    "hexagon": "hexagon",
    "hex": "hexagon",
    "diamond": "diamond",
    "triangle": "triangle",
    "infinity": "infinity",
    "heart": "heart",
    "audio ribbon": "audio_ribbon",
    "audio-ribbon": "audio_ribbon",
    "audio_ribbon": "audio_ribbon",
    "ribbon": "audio_ribbon",
    "spiral": "spiral",
    "tunnel": "tunnel",
    "ring": "ring",
    "starburst": "starburst",
    "soft_eq": "soft_eq",
    "soft eq": "soft_eq",
    "soft-eq": "soft_eq",
    "pillars": "soft_eq",
    "pillar": "soft_eq",
    "rounded bars": "soft_eq",
    "eq": "soft_eq",
    # Legacy Camxora style ids → nearest geometry
    "orbit-spikes": "bars",
    "straight-bars": "bars",
    "signal-needles": "bars",
    "aurora-ribbon": "audio_ribbon",
    "magma-ridge": "wave",
    "plasma-bloom": "circle",
    "contour-waves": "wave",
}


def list_spectrum_shape_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in SPECTRUM_SHAPE_CATALOG)


def normalize_spectrum_shape_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in SPECTRUM_SHAPE_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _SHAPE_ALIASES:
        return _SHAPE_ALIASES[spaced]
    if raw in _SHAPE_ALIASES:
        return _SHAPE_ALIASES[raw]
    if compact in _SHAPE_ALIASES:
        return _SHAPE_ALIASES[compact]
    return None


def _base_layer() -> dict[str, Any]:
    return {
        "id": "shape-layer-1",
        "name": "Shape",
        "enabled": True,
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 4.0,
        "thickness": 36.0,
        "gravity": "outward",
        "glow": 0,
        "blur": 0,
        "opacity": 1.0,
        "blend_mode": "normal",
        "pathMode": "auto",
        "radiusOffset": 0.0,
    }


def spectrum_shape_layer_recipe(shape_id: str) -> list[dict[str, Any]]:
    """Geometry-only layer stack for a shape id."""
    key = normalize_spectrum_shape_id(shape_id) or "bars"
    layer = _base_layer()

    if key == "bars":
        layer.update({"curved": False, "mirrored": False, "gravity": "top", "pathMode": "auto", "barWidth": 5.0})
        return [layer]
    if key == "soft_eq":
        layer.update(
            {
                "curved": False,
                "mirrored": False,
                "gravity": "top",
                "pathMode": "auto",
                "barWidth": 2.4,
                "thickness": 52.0,
                "stylePreset": "soft-eq",
                "roundCaps": True,
                "tipTaper": 0.0,
            }
        )
        return [layer]
    if key == "wave":
        layer.update(
            {
                "curved": True,
                "mirrored": True,
                "gravity": "outward",
                "pathMode": "circle",
                "barWidth": 2.4,
                "thickness": 48.0,
                "stylePreset": "aurora-ribbon",
                "fillCircle": False,
            }
        )
        return [layer]
    if key == "audio_ribbon":
        layer.update(
            {
                "curved": True,
                "mirrored": True,
                "gravity": "outward",
                "pathMode": "circle",
                "barWidth": 1.8,
                "thickness": 26.0,
                "stylePreset": "soft-waveform",
                "fillCircle": False,
            }
        )
        return [layer]
    if key == "circle":
        layer.update(
            {
                "curved": True,
                "mirrored": True,
                "gravity": "outward",
                "pathMode": "circle",
                "barWidth": 4.0,
                "thickness": 34.0,
            }
        )
        return [layer]
    if key == "ring":
        layer.update(
            {
                "curved": True,
                "mirrored": True,
                "gravity": "outward",
                "pathMode": "circle",
                "barWidth": 2.0,
                "thickness": 18.0,
                "fillCircle": False,
            }
        )
        return [layer]
    if key == "starburst":
        layer.update(
            {
                "curved": True,
                "mirrored": True,
                "gravity": "outward",
                "pathMode": "circle",
                "barWidth": 3.0,
                "thickness": 52.0,
            }
        )
        return [layer]
    if key == "double_circle":
        inner = deepcopy(layer)
        outer = deepcopy(layer)
        inner.update(
            {
                "id": "shape-layer-inner",
                "name": "Inner Circle",
                "curved": True,
                "mirrored": True,
                "gravity": "outward",
                "pathMode": "circle",
                "radiusOffset": 0.0,
                "barWidth": 3.5,
                "thickness": 28.0,
            }
        )
        outer.update(
            {
                "id": "shape-layer-outer",
                "name": "Outer Circle",
                "curved": True,
                "mirrored": True,
                "gravity": "outward",
                "pathMode": "circle",
                "radiusOffset": 28.0,
                "barWidth": 3.0,
                "thickness": 24.0,
            }
        )
        return [inner, outer]

    path_map = {
        "hexagon": "hexagon",
        "diamond": "diamond",
        "triangle": "triangle",
        "heart": "heart",
        "infinity": "infinity",
        "spiral": "spiral",
        "tunnel": "tunnel",
    }
    path = path_map.get(key, "circle")
    ribbon = key in ("heart", "infinity", "spiral", "tunnel")
    layer.update(
        {
            "curved": True,
            "mirrored": True,
            "gravity": "outward",
            "pathMode": path,
            "barWidth": 2.2 if ribbon else 3.5,
            "thickness": 36.0 if ribbon else 32.0,
            "stylePreset": "soft-waveform" if ribbon else "orbit-spikes",
            "fillCircle": False,
        }
    )
    return [layer]


def legacy_style_alias_for_shape(shape_id: str) -> str:
    """Map geometry id → a legacy ``style`` the GPU already understands for draw mode."""
    key = normalize_spectrum_shape_id(shape_id) or "bars"
    if key == "wave":
        return "aurora-ribbon"
    if key == "audio_ribbon":
        return "soft-waveform"
    if key in ("heart", "infinity", "spiral", "tunnel"):
        return "soft-waveform"
    if key == "soft_eq":
        return "soft-eq"
    if key in ("circle", "double_circle", "ring", "starburst", "hexagon", "diamond", "triangle"):
        return "orbit-spikes"
    return "orbit-spikes"


def apply_spectrum_shape_to_template(template: dict[str, Any], shape_id: str) -> dict[str, Any]:
    """Apply geometry shape independently of material / palette colors."""
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    key = normalize_spectrum_shape_id(shape_id)
    if key is None:
        raise ValueError(f"unknown spectrum shape: {shape_id!r}")

    ensure_composition_on_template(template)
    prev_material = template["composition"]["spectrum"]["material"]
    prev_animation = template["composition"]["spectrum"]["animation"]
    prev_palette = template["composition"].get("colorPalette")

    # Preserve existing layer colors when replacing geometry stack.
    old_layers = template.get("layers") if isinstance(template.get("layers"), list) else []
    color_bank: list[dict[str, Any]] = []
    for layer in old_layers:
        if isinstance(layer, dict) and isinstance(layer.get("color"), dict):
            color_bank.append(deepcopy(layer["color"]))

    recipe = spectrum_shape_layer_recipe(key)
    for index, layer in enumerate(recipe):
        if index < len(color_bank):
            layer["color"] = deepcopy(color_bank[index])
        elif color_bank:
            layer["color"] = deepcopy(color_bank[0])

    template["layers"] = recipe
    template["style"] = legacy_style_alias_for_shape(key)
    template["spectrumEnabled"] = True

    # Keep primary spectrum instance layers in sync when present.
    instances = template.get("spectrumInstances")
    if isinstance(instances, list) and instances and isinstance(instances[0], dict):
        instances[0] = {
            **instances[0],
            "style": template["style"],
            "layers": deepcopy(recipe),
        }

    scene = apply_spectrum_axes(
        template.get("composition"),
        shape=key,
        material=prev_material,
        animation=prev_animation,
    )
    if prev_palette:
        scene["colorPalette"] = prev_palette
    template["composition"] = normalize_composition_scene(scene)
    return template
