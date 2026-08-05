"""Spectrum material catalog (20) — look uniforms."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

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
    ("chrome", "Chrome", {"glow": 8.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False}),
    ("matte", "Matte", {"glow": 0.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False}),
    ("velvet", "Velvet", {"glow": 3.0, "blur": 1.0, "blend_mode": "normal", "opacity": 0.9, "fillCircle": False}),
    ("obsidian", "Obsidian", {"glow": 1.0, "blur": 0.0, "blend_mode": "normal", "opacity": 0.95, "fillCircle": True}),
    ("iridescent", "Iridescent", {"glow": 15.0, "blur": 1.5, "blend_mode": "add", "opacity": 0.85, "fillCircle": False}),
    ("latex", "Latex", {"glow": 5.0, "blur": 0.5, "blend_mode": "normal", "opacity": 0.88, "fillCircle": False}),
    ("frosted_glass", "Frosted Glass", {"glow": 7.0, "blur": 4.0, "blend_mode": "normal", "opacity": 0.7, "fillCircle": True}),
    ("wireframe", "Wireframe", {"glow": 0.0, "blur": 0.0, "blend_mode": "normal", "opacity": 1.0, "fillCircle": False, "barWidth": 1.4}),
)

SPECTRUM_MATERIAL_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {"id": row[0], "label": row[1], "uniforms": dict(row[2])} for row in _MATERIAL_ROWS
)
SPECTRUM_MATERIAL_IDS: frozenset[str] = frozenset(item["id"] for item in SPECTRUM_MATERIAL_CATALOG)
SPECTRUM_MATERIAL_COUNT = len(SPECTRUM_MATERIAL_CATALOG)
assert SPECTRUM_MATERIAL_COUNT == 20, SPECTRUM_MATERIAL_COUNT

MATERIAL_UNIFORM_KEYS: frozenset[str] = frozenset(
    {"glow", "blur", "blend_mode", "opacity", "fillCircle", "barWidth"}
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
