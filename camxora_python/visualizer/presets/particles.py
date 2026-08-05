"""Particle type catalog (20) — distinct emitter profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Each type is a first-class emitter profile (travel/spawn/size), not a GPU variant bag.
_TYPE_ROWS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("dust", "Dust", {"style": "glow", "spawnArea": "full", "travelMode": "spawnFlow", "speed": 1.1, "lifetimeSec": 5.2, "size": 8.2, "opacity": 0.48, "maxCount": 920, "spawnRate": 320, "drift": 0.52, "swirl": 0.22, "sizeJitter": 0.82, "color": "#f7ede2"}),
    ("snow", "Snow", {"style": "glow", "spawnArea": "full", "travelMode": "fall", "speed": 0.85, "lifetimeSec": 6.5, "size": 6.5, "opacity": 0.7, "maxCount": 700, "spawnRate": 240, "drift": 0.45, "swirl": 0.08, "sizeJitter": 0.55, "color": "#e8f4ff"}),
    ("rain", "Rain", {"style": "dot", "spawnArea": "full", "travelMode": "fall", "speed": 5.5, "lifetimeSec": 1.4, "size": 2.2, "opacity": 0.55, "maxCount": 1100, "spawnRate": 680, "drift": 0.12, "swirl": 0.02, "sizeJitter": 0.25, "color": "#9ec9ff"}),
    ("fire", "Fire", {"style": "spark", "spawnArea": "bottom", "travelMode": "rise", "speed": 3.2, "lifetimeSec": 1.4, "size": 5.8, "opacity": 0.92, "maxCount": 520, "spawnRate": 360, "drift": 0.28, "swirl": 0.12, "sizeJitter": 0.5, "color": "#ff6a1a"}),
    ("smoke", "Smoke", {"style": "glow", "spawnArea": "bottom", "travelMode": "rise", "speed": 0.9, "lifetimeSec": 7.0, "size": 14.0, "opacity": 0.35, "maxCount": 280, "spawnRate": 90, "drift": 0.4, "swirl": 0.35, "sizeJitter": 0.7, "color": "#a8a8b8"}),
    ("magic", "Magic", {"style": "bokeh", "spawnArea": "screenCenter", "travelMode": "rise", "speed": 1.2, "lifetimeSec": 5.5, "size": 12.0, "opacity": 0.55, "maxCount": 360, "spawnRate": 160, "drift": 0.3, "swirl": 0.32, "sizeJitter": 0.65, "color": "#c084fc"}),
    ("electric", "Electric", {"style": "spark", "spawnArea": "centerRing", "travelMode": "burst", "speed": 6.4, "lifetimeSec": 0.95, "size": 4.0, "opacity": 1.0, "maxCount": 720, "spawnRate": 640, "drift": 0.08, "swirl": 0.18, "sizeJitter": 0.4, "color": "#64e5ff"}),
    ("stars", "Stars", {"style": "spark", "spawnArea": "full", "travelMode": "spawnFlow", "speed": 0.55, "lifetimeSec": 4.8, "size": 3.2, "opacity": 0.85, "maxCount": 500, "spawnRate": 140, "drift": 0.15, "swirl": 0.05, "sizeJitter": 0.45, "color": "#ffe9a8"}),
    ("bubbles", "Bubbles", {"style": "ring", "spawnArea": "centerRing", "travelMode": "rise", "speed": 1.15, "lifetimeSec": 5.8, "size": 10.5, "opacity": 0.5, "maxCount": 300, "spawnRate": 120, "drift": 0.25, "swirl": 0.5, "sizeJitter": 0.55, "color": "#d6f4ff"}),
    ("ash", "Ash", {"style": "glow", "spawnArea": "full", "travelMode": "fall", "speed": 0.7, "lifetimeSec": 6.0, "size": 5.5, "opacity": 0.4, "maxCount": 480, "spawnRate": 180, "drift": 0.5, "swirl": 0.18, "sizeJitter": 0.6, "color": "#8a8680"}),
    ("confetti", "Confetti", {"style": "dot", "spawnArea": "screenCenter", "travelMode": "burst", "speed": 4.2, "lifetimeSec": 2.2, "size": 4.5, "opacity": 0.95, "maxCount": 600, "spawnRate": 420, "drift": 0.35, "swirl": 0.4, "sizeJitter": 0.7, "color": "#ff5c8a"}),
    ("leaves", "Leaves", {"style": "dot", "spawnArea": "full", "travelMode": "fall", "speed": 1.0, "lifetimeSec": 5.5, "size": 7.0, "opacity": 0.75, "maxCount": 260, "spawnRate": 70, "drift": 0.65, "swirl": 0.45, "sizeJitter": 0.55, "color": "#c45c26"}),
    ("sparkles", "Sparkles", {"style": "spark", "spawnArea": "centerRing", "travelMode": "burst", "speed": 5.8, "lifetimeSec": 0.85, "size": 3.6, "opacity": 1.0, "maxCount": 640, "spawnRate": 700, "drift": 0.06, "swirl": 0.1, "sizeJitter": 0.35, "color": "#ffffff"}),
    ("embers", "Embers", {"style": "spark", "spawnArea": "bottom", "travelMode": "rise", "speed": 2.4, "lifetimeSec": 1.65, "size": 5.4, "opacity": 0.88, "maxCount": 420, "spawnRate": 280, "drift": 0.32, "swirl": 0.06, "sizeJitter": 0.52, "color": "#ff9a3c"}),
    ("petals", "Petals", {"style": "dot", "spawnArea": "full", "travelMode": "fall", "speed": 0.95, "lifetimeSec": 5.8, "size": 6.8, "opacity": 0.72, "maxCount": 320, "spawnRate": 90, "drift": 0.7, "swirl": 0.38, "sizeJitter": 0.5, "color": "#ff8fab"}),
    ("glitter", "Glitter", {"style": "spark", "spawnArea": "screenRandom", "travelMode": "random", "speed": 1.6, "lifetimeSec": 2.4, "size": 2.8, "opacity": 0.95, "maxCount": 800, "spawnRate": 380, "drift": 0.2, "swirl": 0.15, "sizeJitter": 0.4, "color": "#f5e6a3"}),
    ("smoke_rings", "Smoke Rings", {"style": "ring", "spawnArea": "centerRing", "travelMode": "rise", "speed": 0.8, "lifetimeSec": 6.2, "size": 16.0, "opacity": 0.32, "maxCount": 180, "spawnRate": 55, "drift": 0.28, "swirl": 0.55, "sizeJitter": 0.45, "color": "#9aa3b2"}),
    ("energy_orbs", "Energy Orbs", {"style": "bokeh", "spawnArea": "centerRing", "travelMode": "spawnFlow", "speed": 2.0, "lifetimeSec": 2.8, "size": 11.0, "opacity": 0.7, "maxCount": 240, "spawnRate": 200, "drift": 0.18, "swirl": 0.42, "sizeJitter": 0.4, "color": "#5eead4"}),
    ("pixel_dust", "Pixel Dust", {"style": "dot", "spawnArea": "full", "travelMode": "spawnFlow", "speed": 1.35, "lifetimeSec": 3.5, "size": 2.0, "opacity": 0.8, "maxCount": 1000, "spawnRate": 450, "drift": 0.25, "swirl": 0.1, "sizeJitter": 0.2, "color": "#94a3b8"}),
    ("feather_drift", "Feather Drift", {"style": "glow", "spawnArea": "full", "travelMode": "fall", "speed": 0.55, "lifetimeSec": 8.0, "size": 9.5, "opacity": 0.42, "maxCount": 220, "spawnRate": 45, "drift": 0.8, "swirl": 0.28, "sizeJitter": 0.75, "color": "#f8f1e7"}),
)

PARTICLE_TYPE_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {"id": row[0], "label": row[1], "emitter": dict(row[2])} for row in _TYPE_ROWS
)
PARTICLE_TYPE_IDS: frozenset[str] = frozenset(item["id"] for item in PARTICLE_TYPE_CATALOG)
PARTICLE_TYPE_COUNT = len(PARTICLE_TYPE_CATALOG)
assert PARTICLE_TYPE_COUNT == 20, PARTICLE_TYPE_COUNT

_BY_ID = {item["id"]: item for item in PARTICLE_TYPE_CATALOG}
_ALIASES = {
    **{item["id"]: item["id"] for item in PARTICLE_TYPE_CATALOG},
    **{item["label"].lower(): item["id"] for item in PARTICLE_TYPE_CATALOG},
    "smoke rings": "smoke_rings",
    "energy orbs": "energy_orbs",
    "pixel dust": "pixel_dust",
    "feather drift": "feather_drift",
}


def list_particle_type_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in PARTICLE_TYPE_CATALOG)


def normalize_particle_type_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in PARTICLE_TYPE_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None


def get_particle_type(type_id: str | None) -> dict[str, Any] | None:
    key = normalize_particle_type_id(type_id)
    if not key:
        return None
    item = _BY_ID[key]
    return {"id": item["id"], "label": item["label"], "emitter": deepcopy(item["emitter"])}
