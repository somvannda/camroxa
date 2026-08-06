"""Lighting effect catalog (15) + trigger axis."""

from __future__ import annotations

from typing import Any

_LIGHTING_ROWS: tuple[tuple[str, str], ...] = (
    ("lightning", "Lightning"),
    ("aura", "Aura"),
    ("glow", "Glow"),
    ("god_rays", "God Rays"),
    ("lens_flare", "Lens Flare"),
    ("light_beam", "Light Beam"),
    ("light_sweep", "Light Sweep"),
    ("neon_rim", "Neon Rim"),
    ("halo", "Halo"),
    ("energy_pulse", "Energy Pulse"),
    ("strobe_flash", "Strobe Flash"),
    ("rim_light", "Rim Light"),
    ("spot_cone", "Spot Cone"),
    ("volumetric_shaft", "Volumetric Shaft"),
    ("color_wash", "Color Wash"),
)

LIGHTING_EFFECT_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _LIGHTING_ROWS
)
LIGHTING_EFFECT_IDS: frozenset[str] = frozenset(item["id"] for item in LIGHTING_EFFECT_CATALOG)
LIGHTING_EFFECT_COUNT = len(LIGHTING_EFFECT_CATALOG)
assert LIGHTING_EFFECT_COUNT == 15, LIGHTING_EFFECT_COUNT

# Triggers are audio-bus ids (or none). Full mapping lives in P11.
_LIGHTING_TRIGGER_ROWS: tuple[tuple[str, str], ...] = (
    ("none", "None"),
    ("bass", "Bass"),
    ("treble", "Treble"),
    ("vocals", "Vocals (heuristic)"),
    ("beat", "Beat"),
    ("melody", "Melody (heuristic)"),
    ("kick", "Kick"),
    ("snare", "Snare (heuristic)"),
    ("overall_loudness", "Overall Loudness"),
)

LIGHTING_TRIGGER_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _LIGHTING_TRIGGER_ROWS
)
LIGHTING_TRIGGER_IDS: frozenset[str] = frozenset(item["id"] for item in LIGHTING_TRIGGER_CATALOG)

_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in LIGHTING_EFFECT_CATALOG},
    **{item["label"].lower(): item["id"] for item in LIGHTING_EFFECT_CATALOG},
    "god rays": "god_rays",
    "lens flare": "lens_flare",
    "light beam": "light_beam",
    "light sweep": "light_sweep",
    "neon rim": "neon_rim",
    "energy pulse": "energy_pulse",
    "strobe flash": "strobe_flash",
    "rim light": "rim_light",
    "spot cone": "spot_cone",
    "volumetric shaft": "volumetric_shaft",
    "color wash": "color_wash",
}


def list_lighting_effect_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in LIGHTING_EFFECT_CATALOG)


def list_lighting_trigger_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in LIGHTING_TRIGGER_CATALOG)


def normalize_lighting_effect_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw or raw == "none":
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in LIGHTING_EFFECT_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None


def normalize_lighting_trigger_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not raw or raw == "none":
        return None
    if raw in LIGHTING_TRIGGER_IDS:
        return raw
    return None
