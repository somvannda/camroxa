"""Spectrum shape catalog (15) — geometry factories."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

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

_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in SPECTRUM_SHAPE_CATALOG},
    **{item["label"].lower(): item["id"] for item in SPECTRUM_SHAPE_CATALOG},
    "double circle": "double_circle",
    "audio ribbon": "audio_ribbon",
    "hex": "hexagon",
    "bar": "bars",
    "pillar": "soft_eq",
    "pillars": "soft_eq",
    "soft eq": "soft_eq",
    "rounded bars": "soft_eq",
    "eq": "soft_eq",
    "ribbon": "audio_ribbon",
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
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
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
        "glow": 0.0,
        "blur": 0.0,
        "opacity": 1.0,
        "blend_mode": "normal",
        "pathMode": "auto",
        "radiusOffset": 0.0,
        "shapeId": "bars",
    }


def build_shape_layers(shape_id: str) -> list[dict[str, Any]]:
    """Build geometry layers for a catalog shape id (engine authority)."""
    key = normalize_spectrum_shape_id(shape_id)
    if key is None:
        raise ValueError(f"unknown spectrum shape: {shape_id!r}")
    layer = _base_layer()
    layer["shapeId"] = key

    if key == "bars":
        layer.update(
            {
                "curved": False,
                "mirrored": False,
                "gravity": "top",
                "pathMode": "auto",
                "barWidth": 5.0,
                "thickness": 40.0,
            }
        )
        return [layer]
    if key == "soft_eq":
        # Thin equal-width linear bars with rounded caps (reference Soft EQ look).
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
                "fillCircle": False,
            }
        )
        return [layer]
    if key == "wave":
        layer.update(
            {
                "curved": True,
                "mirrored": True,
                "gravity": "center",
                "pathMode": "auto",
                "barWidth": 2.4,
                "thickness": 48.0,
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
                "radiusOffset": 12.0,
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
                "radiusOffset": 0.0,
                "fillCircle": True,
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
                "barWidth": 1.6,
                "thickness": 14.0,
                "radiusOffset": 22.0,
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
                "barWidth": 2.2,
                "thickness": 72.0,
                "radiusOffset": -6.0,
                "fillCircle": False,
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
                "shapeId": key,
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
                "shapeId": key,
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
    layer.update(
        {
            "curved": True,
            "mirrored": True,
            "gravity": "outward",
            "pathMode": path,
            "barWidth": 3.5,
            "thickness": 32.0,
        }
    )
    return [layer]
