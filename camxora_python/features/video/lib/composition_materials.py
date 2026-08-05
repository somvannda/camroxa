"""Composition Engine P4 — spectrum materials (20 look packs).

Materials are parameter packs (glow / blur / blend / edge), not separate shape
assets. Same ``composition.spectrum.shape`` + different ``material`` ⇒ Neon Circle
vs Glass Circle without four spectrum geometries.
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

# (id, label, look patch applied onto each spectrum layer)
# Look keys only — never curved / pathMode / mirrored (those are shape).
_MATERIAL_ROWS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("neon", "Neon", {"glow": 22.0, "blur": 0.0, "blend_mode": "add", "opacity": 1.0, "fillCircle": False}),
    ("glass", "Glass", {"glow": 6.0, "blur": 2.0, "blend_mode": "normal", "opacity": 0.72, "fillCircle": True}),
    ("crystal", "Crystal", {"glow": 14.0, "blur": 1.0, "blend_mode": "add", "opacity": 0.88, "fillCircle": True}),
    ("electric", "Electric", {"glow": 18.0, "blur": 0.0, "blend_mode": "add", "opacity": 1.0, "fillCircle": False}),
    ("fire", "Fire", {"glow": 20.0, "blur": 1.5, "blend_mode": "add", "opacity": 0.95, "fillCircle": False}),
    ("ice", "Ice", {"glow": 10.0, "blur": 2.5, "blend_mode": "normal", "opacity": 0.85, "fillCircle": True}),
    ("metal", "Metal", {"glow": 4.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False}),
    ("liquid", "Liquid", {"glow": 8.0, "blur": 3.0, "blend_mode": "normal", "opacity": 0.8, "fillCircle": False}),
    ("plasma", "Plasma", {"glow": 26.0, "blur": 1.0, "blend_mode": "add", "opacity": 1.0, "fillCircle": True}),
    ("gold", "Gold", {"glow": 12.0, "blur": 0.5, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False}),
    ("hologram", "Hologram", {"glow": 16.0, "blur": 2.0, "blend_mode": "add", "opacity": 0.65, "fillCircle": False}),
    ("carbon", "Carbon", {"glow": 2.0, "blur": 0.0, "blend_mode": "normal", "opacity": 0.92, "fillCircle": False}),
    # Fill → 20
    ("chrome", "Chrome", {"glow": 8.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False}),
    ("matte", "Matte", {"glow": 0.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False}),
    ("velvet", "Velvet", {"glow": 3.0, "blur": 1.0, "blend_mode": "normal", "opacity": 0.9, "fillCircle": False}),
    ("obsidian", "Obsidian", {"glow": 1.0, "blur": 0.0, "blend_mode": "normal", "opacity": 0.95, "fillCircle": True}),
    ("iridescent", "Iridescent", {"glow": 15.0, "blur": 1.5, "blend_mode": "add", "opacity": 0.85, "fillCircle": False}),
    ("latex", "Latex", {"glow": 5.0, "blur": 0.5, "blend_mode": "normal", "opacity": 0.88, "fillCircle": False}),
    ("frosted_glass", "Frosted Glass", {"glow": 7.0, "blur": 4.0, "blend_mode": "normal", "opacity": 0.7, "fillCircle": True}),
    ("wireframe", "Wireframe", {"glow": 0.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False, "barWidth": 1.4}),
)

MATERIAL_LOOK_KEYS: frozenset[str] = frozenset(
    {"glow", "blur", "blend_mode", "opacity", "fillCircle", "barWidth"}
)

SPECTRUM_MATERIAL_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {
        "id": row[0],
        "label": row[1],
        "look": dict(row[2]),
    }
    for row in _MATERIAL_ROWS
)

SPECTRUM_MATERIAL_IDS: frozenset[str] = frozenset(item["id"] for item in SPECTRUM_MATERIAL_CATALOG)
SPECTRUM_MATERIAL_COUNT = len(SPECTRUM_MATERIAL_CATALOG)
assert SPECTRUM_MATERIAL_COUNT == 20, SPECTRUM_MATERIAL_COUNT

_MATERIAL_BY_ID: dict[str, dict[str, Any]] = {item["id"]: item for item in SPECTRUM_MATERIAL_CATALOG}

_MATERIAL_ALIASES: dict[str, str] = {
    "neon": "neon",
    "glass": "glass",
    "crystal": "crystal",
    "electric": "electric",
    "fire": "fire",
    "ice": "ice",
    "metal": "metal",
    "liquid": "liquid",
    "plasma": "plasma",
    "gold": "gold",
    "hologram": "hologram",
    "carbon": "carbon",
    "chrome": "chrome",
    "matte": "matte",
    "velvet": "velvet",
    "obsidian": "obsidian",
    "iridescent": "iridescent",
    "latex": "latex",
    "frosted glass": "frosted_glass",
    "frosted-glass": "frosted_glass",
    "frosted_glass": "frosted_glass",
    "wireframe": "wireframe",
}


def list_spectrum_material_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in SPECTRUM_MATERIAL_CATALOG)


def normalize_spectrum_material_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in SPECTRUM_MATERIAL_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _MATERIAL_ALIASES:
        return _MATERIAL_ALIASES[spaced]
    if raw in _MATERIAL_ALIASES:
        return _MATERIAL_ALIASES[raw]
    return None


def get_spectrum_material(material_id: str | None) -> dict[str, Any] | None:
    key = normalize_spectrum_material_id(material_id)
    if not key:
        return None
    return deepcopy(_MATERIAL_BY_ID[key])


def _paint_layer_material(layer: Any, look: dict[str, Any]) -> Any:
    if not isinstance(layer, dict):
        return layer
    out = deepcopy(layer)
    for key, value in look.items():
        if key in MATERIAL_LOOK_KEYS:
            out[key] = deepcopy(value) if isinstance(value, (dict, list)) else value
    return out


def apply_spectrum_material_to_template(template: dict[str, Any], material_id: str) -> dict[str, Any]:
    """Apply material look pack without changing shape / path / palette colors."""
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    material = get_spectrum_material(material_id)
    if material is None:
        raise ValueError(f"unknown spectrum material: {material_id!r}")

    ensure_composition_on_template(template)
    prev_shape = template["composition"]["spectrum"]["shape"]
    prev_animation = template["composition"]["spectrum"]["animation"]
    prev_palette = template["composition"].get("colorPalette")
    look = material["look"]

    layers = template.get("layers")
    if isinstance(layers, list):
        template["layers"] = [_paint_layer_material(layer, look) for layer in layers]

    instances = template.get("spectrumInstances")
    if isinstance(instances, list):
        next_instances: list[Any] = []
        for inst in instances:
            if not isinstance(inst, dict):
                next_instances.append(inst)
                continue
            cloned = deepcopy(inst)
            inst_layers = cloned.get("layers")
            if isinstance(inst_layers, list):
                cloned["layers"] = [_paint_layer_material(layer, look) for layer in inst_layers]
            next_instances.append(cloned)
        template["spectrumInstances"] = next_instances

    scene = apply_spectrum_axes(
        template.get("composition"),
        shape=prev_shape if prev_shape else NONE,
        material=material["id"],
        animation=prev_animation,
    )
    if prev_palette:
        scene["colorPalette"] = prev_palette
    # If shape was none, keep none explicitly
    if not prev_shape or prev_shape == NONE:
        scene["spectrum"]["shape"] = NONE
    template["composition"] = normalize_composition_scene(scene)
    return template
