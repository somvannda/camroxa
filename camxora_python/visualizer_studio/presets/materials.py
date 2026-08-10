"""Spectrum material catalog (20) — look uniforms."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# glow is preview-native (0..100 scale via /100 in paint). barWidth/thickness make
# materials visibly distinct beyond glow alone.
_MATERIAL_ROWS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("neon", "Neon", {"glow": 55.0, "blur": 0.0, "blend_mode": "add", "opacity": 1.0, "fillCircle": False, "barWidth": 3.2, "thickness": 38.0}),
    ("glass", "Glass", {"glow": 18.0, "blur": 3.5, "blend_mode": "normal", "opacity": 0.68, "fillCircle": True, "barWidth": 5.5, "thickness": 30.0}),
    ("crystal", "Crystal", {"glow": 40.0, "blur": 1.5, "blend_mode": "add", "opacity": 0.88, "fillCircle": True, "barWidth": 3.8, "thickness": 34.0}),
    ("electric", "Electric", {"glow": 48.0, "blur": 0.0, "blend_mode": "add", "opacity": 1.0, "fillCircle": False, "barWidth": 2.4, "thickness": 46.0}),
    ("fire", "Fire", {"glow": 52.0, "blur": 2.2, "blend_mode": "add", "opacity": 0.95, "fillCircle": False, "barWidth": 4.2, "thickness": 42.0}),
    ("ice", "Ice", {"glow": 28.0, "blur": 3.0, "blend_mode": "normal", "opacity": 0.82, "fillCircle": True, "barWidth": 4.8, "thickness": 28.0}),
    ("metal", "Metal", {"glow": 12.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False, "barWidth": 5.0, "thickness": 32.0}),
    ("liquid", "Liquid", {"glow": 22.0, "blur": 4.0, "blend_mode": "normal", "opacity": 0.78, "fillCircle": False, "barWidth": 6.0, "thickness": 36.0}),
    ("plasma", "Plasma", {"glow": 70.0, "blur": 1.8, "blend_mode": "add", "opacity": 1.0, "fillCircle": True, "barWidth": 3.0, "thickness": 48.0}),
    ("gold", "Gold", {"glow": 34.0, "blur": 0.8, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False, "barWidth": 4.6, "thickness": 33.0}),
    ("hologram", "Hologram", {"glow": 44.0, "blur": 2.5, "blend_mode": "add", "opacity": 0.62, "fillCircle": False, "barWidth": 2.8, "thickness": 40.0}),
    ("carbon", "Carbon", {"glow": 6.0, "blur": 0.0, "blend_mode": "normal", "opacity": 0.92, "fillCircle": False, "barWidth": 5.2, "thickness": 30.0}),
    ("chrome", "Chrome", {"glow": 26.0, "blur": 0.4, "blend_mode": "add", "opacity": 1.0, "fillCircle": False, "barWidth": 3.6, "thickness": 34.0}),
    ("matte", "Matte", {"glow": 0.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False, "barWidth": 5.5, "thickness": 28.0}),
    ("velvet", "Velvet", {"glow": 8.0, "blur": 1.8, "blend_mode": "normal", "opacity": 0.9, "fillCircle": False, "barWidth": 6.2, "thickness": 26.0}),
    ("obsidian", "Obsidian", {"glow": 4.0, "blur": 0.0, "blend_mode": "normal", "opacity": 0.95, "fillCircle": True, "barWidth": 4.4, "thickness": 31.0}),
    ("iridescent", "Iridescent", {"glow": 42.0, "blur": 2.0, "blend_mode": "add", "opacity": 0.85, "fillCircle": False, "barWidth": 3.4, "thickness": 37.0}),
    ("latex", "Latex", {"glow": 14.0, "blur": 0.8, "blend_mode": "normal", "opacity": 0.88, "fillCircle": False, "barWidth": 5.8, "thickness": 29.0}),
    ("frosted_glass", "Frosted Glass", {"glow": 20.0, "blur": 5.0, "blend_mode": "normal", "opacity": 0.66, "fillCircle": True, "barWidth": 5.0, "thickness": 27.0}),
    ("wireframe", "Wireframe", {"glow": 2.0, "blur": 0.0, "blend_mode": "add", "opacity": 1.0, "fillCircle": False, "barWidth": 1.2, "thickness": 44.0}),
)

SPECTRUM_MATERIAL_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {"id": row[0], "label": row[1], "uniforms": dict(row[2])} for row in _MATERIAL_ROWS
)
SPECTRUM_MATERIAL_IDS: frozenset[str] = frozenset(item["id"] for item in SPECTRUM_MATERIAL_CATALOG)
SPECTRUM_MATERIAL_COUNT = len(SPECTRUM_MATERIAL_CATALOG)
assert SPECTRUM_MATERIAL_COUNT == 20, SPECTRUM_MATERIAL_COUNT

MATERIAL_UNIFORM_KEYS: frozenset[str] = frozenset(
    {"glow", "blur", "blend_mode", "opacity", "fillCircle", "barWidth", "thickness"}
)

_BY_ID = {item["id"]: item for item in SPECTRUM_MATERIAL_CATALOG}
_ALIASES = {
    **{item["id"]: item["id"] for item in SPECTRUM_MATERIAL_CATALOG},
    **{item["label"].lower(): item["id"] for item in SPECTRUM_MATERIAL_CATALOG},
    "frosted glass": "frosted_glass",
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
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None


def get_material(material_id: str | None) -> dict[str, Any] | None:
    key = normalize_spectrum_material_id(material_id)
    if not key:
        return None
    item = _BY_ID[key]
    return {"id": item["id"], "label": item["label"], "uniforms": deepcopy(item["uniforms"])}
