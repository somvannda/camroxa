"""Material resolve — apply uniforms onto spectrum geometry layers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer.presets.materials import (
    MATERIAL_UNIFORM_KEYS,
    SPECTRUM_MATERIAL_COUNT,
    SPECTRUM_MATERIAL_IDS,
    get_material,
    normalize_spectrum_material_id,
)


def apply_material_to_layers(layers: list[dict[str, Any]], material_id: str | None) -> list[dict[str, Any]]:
    material = get_material(material_id)
    if material is None:
        return [deepcopy(layer) for layer in layers]
    uniforms = material["uniforms"]
    out: list[dict[str, Any]] = []
    for layer in layers:
        cloned = deepcopy(layer)
        for key, value in uniforms.items():
            if key in MATERIAL_UNIFORM_KEYS:
                cloned[key] = deepcopy(value) if isinstance(value, (dict, list)) else value
        cloned["materialId"] = material["id"]
        out.append(cloned)
    return out


__all__ = (
    "SPECTRUM_MATERIAL_COUNT",
    "SPECTRUM_MATERIAL_IDS",
    "apply_material_to_layers",
    "get_material",
    "normalize_spectrum_material_id",
)
