"""Composition Engine P6 — particle types (20).

``composition.particles.type`` is the semantic catalog id (Dust … Feather Drift).
Applying a type writes a GPU-safe ``particlesSettings`` recipe (variant/style/
travel/…) and does **not** clear ``composition.particles.behavior``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from features.video.lib.composition_axes import apply_particles_axes
from features.video.lib.composition_scene_contract import (
    NONE,
    ensure_composition_on_template,
    normalize_composition_scene,
)

# recipe keys written onto particlesSettings (not behavior / not color when preserving)
_TYPE_RECIPE_KEYS: frozenset[str] = frozenset(
    {
        "enabled",
        "variant",
        "style",
        "spawnArea",
        "travelMode",
        "spawnMode",
        "speed",
        "lifetimeSec",
        "size",
        "opacity",
        "reactivity",
        "audioMotionMode",
        "audioTravelBoost",
        "maxCount",
        "spawnRate",
        "smoothing",
        "spawnTrigger",
        "spawnThreshold",
        "sizeJitter",
        "drift",
        "swirl",
        "reactStrength",
        "glow",
    }
)

_COLOR_KEYS: frozenset[str] = frozenset(
    {"color", "reactColor", "colorMode", "paletteColors"}
)

# (id, label, particlesSettings recipe) — variant must be classic|bokeh|soap|dust
_TYPE_ROWS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "dust",
        "Dust",
        {
            "enabled": True,
            "variant": "dust",
            "style": "glow",
            "spawnArea": "full",
            "travelMode": "spawnFlow",
            "spawnMode": "always",
            "speed": 1.1,
            "lifetimeSec": 5.2,
            "size": 8.2,
            "opacity": 0.48,
            "reactivity": 0.22,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.0,
            "maxCount": 920,
            "spawnRate": 320,
            "smoothing": 0.58,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.08,
            "sizeJitter": 0.82,
            "drift": 0.52,
            "swirl": 0.22,
            "reactStrength": 0.42,
            "glow": 0.2,
            "color": "#f7ede2",
            "reactColor": "#fff8ef",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "snow",
        "Snow",
        {
            "enabled": True,
            "variant": "dust",
            "style": "glow",
            "spawnArea": "full",
            "travelMode": "fall",
            "spawnMode": "always",
            "speed": 0.85,
            "lifetimeSec": 6.5,
            "size": 6.5,
            "opacity": 0.7,
            "reactivity": 0.12,
            "audioMotionMode": "travel",
            "audioTravelBoost": 0.8,
            "maxCount": 700,
            "spawnRate": 240,
            "smoothing": 0.7,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.12,
            "sizeJitter": 0.55,
            "drift": 0.45,
            "swirl": 0.08,
            "reactStrength": 0.3,
            "glow": 0.15,
            "color": "#e8f4ff",
            "reactColor": "#ffffff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "rain",
        "Rain",
        {
            "enabled": True,
            "variant": "classic",
            "style": "dot",
            "spawnArea": "full",
            "travelMode": "fall",
            "spawnMode": "always",
            "speed": 5.5,
            "lifetimeSec": 1.4,
            "size": 2.2,
            "opacity": 0.55,
            "reactivity": 0.18,
            "audioMotionMode": "travel",
            "audioTravelBoost": 1.2,
            "maxCount": 1100,
            "spawnRate": 680,
            "smoothing": 0.2,
            "spawnTrigger": "both",
            "spawnThreshold": 0.06,
            "sizeJitter": 0.25,
            "drift": 0.12,
            "swirl": 0.02,
            "reactStrength": 0.35,
            "glow": 0.0,
            "color": "#9ec9ff",
            "reactColor": "#dcefff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "fire",
        "Fire",
        {
            "enabled": True,
            "variant": "classic",
            "style": "spark",
            "spawnArea": "bottom",
            "travelMode": "rise",
            "spawnMode": "reactiveOnly",
            "speed": 3.2,
            "lifetimeSec": 1.4,
            "size": 5.8,
            "opacity": 0.92,
            "reactivity": 0.45,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.1,
            "maxCount": 520,
            "spawnRate": 360,
            "smoothing": 0.14,
            "spawnTrigger": "both",
            "spawnThreshold": 0.04,
            "sizeJitter": 0.5,
            "drift": 0.28,
            "swirl": 0.12,
            "reactStrength": 0.8,
            "glow": 0.55,
            "color": "#ff6a1a",
            "reactColor": "#ffe08a",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "smoke",
        "Smoke",
        {
            "enabled": True,
            "variant": "dust",
            "style": "glow",
            "spawnArea": "bottom",
            "travelMode": "rise",
            "spawnMode": "always",
            "speed": 0.9,
            "lifetimeSec": 7.0,
            "size": 14.0,
            "opacity": 0.35,
            "reactivity": 0.2,
            "audioMotionMode": "both",
            "audioTravelBoost": 0.9,
            "maxCount": 280,
            "spawnRate": 90,
            "smoothing": 0.75,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.1,
            "sizeJitter": 0.7,
            "drift": 0.4,
            "swirl": 0.35,
            "reactStrength": 0.4,
            "glow": 0.3,
            "color": "#a8a8b8",
            "reactColor": "#d0d0dc",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "magic",
        "Magic",
        {
            "enabled": True,
            "variant": "bokeh",
            "style": "bokeh",
            "spawnArea": "screenCenter",
            "travelMode": "rise",
            "spawnMode": "always",
            "speed": 1.2,
            "lifetimeSec": 5.5,
            "size": 12.0,
            "opacity": 0.55,
            "reactivity": 0.28,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.0,
            "maxCount": 360,
            "spawnRate": 160,
            "smoothing": 0.62,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.09,
            "sizeJitter": 0.65,
            "drift": 0.3,
            "swirl": 0.32,
            "reactStrength": 0.55,
            "glow": 0.4,
            "color": "#c084fc",
            "reactColor": "#ffffff",
            "colorMode": "palette",
            "paletteColors": ["#c084fc", "#60a5fa", "#f472b6", "#ffffff"],
        },
    ),
    (
        "electric",
        "Electric",
        {
            "enabled": True,
            "variant": "classic",
            "style": "spark",
            "spawnArea": "centerRing",
            "travelMode": "burst",
            "spawnMode": "reactiveOnly",
            "speed": 6.4,
            "lifetimeSec": 0.95,
            "size": 4.0,
            "opacity": 1.0,
            "reactivity": 0.6,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.2,
            "maxCount": 720,
            "spawnRate": 640,
            "smoothing": 0.08,
            "spawnTrigger": "kick",
            "spawnThreshold": 0.02,
            "sizeJitter": 0.4,
            "drift": 0.08,
            "swirl": 0.18,
            "reactStrength": 0.95,
            "glow": 0.7,
            "color": "#64e5ff",
            "reactColor": "#ffffff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "stars",
        "Stars",
        {
            "enabled": True,
            "variant": "classic",
            "style": "spark",
            "spawnArea": "full",
            "travelMode": "spawnFlow",
            "spawnMode": "always",
            "speed": 0.55,
            "lifetimeSec": 4.8,
            "size": 3.2,
            "opacity": 0.85,
            "reactivity": 0.25,
            "audioMotionMode": "sizePulse",
            "audioTravelBoost": 0.6,
            "maxCount": 500,
            "spawnRate": 140,
            "smoothing": 0.55,
            "spawnTrigger": "both",
            "spawnThreshold": 0.1,
            "sizeJitter": 0.45,
            "drift": 0.15,
            "swirl": 0.05,
            "reactStrength": 0.5,
            "glow": 0.6,
            "color": "#ffe9a8",
            "reactColor": "#ffffff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "bubbles",
        "Bubbles",
        {
            "enabled": True,
            "variant": "soap",
            "style": "ring",
            "spawnArea": "centerRing",
            "travelMode": "rise",
            "spawnMode": "always",
            "speed": 1.15,
            "lifetimeSec": 5.8,
            "size": 10.5,
            "opacity": 0.5,
            "reactivity": 0.22,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.0,
            "maxCount": 300,
            "spawnRate": 120,
            "smoothing": 0.65,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.08,
            "sizeJitter": 0.55,
            "drift": 0.25,
            "swirl": 0.5,
            "reactStrength": 0.48,
            "glow": 0.25,
            "color": "#d6f4ff",
            "reactColor": "#ffffff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "ash",
        "Ash",
        {
            "enabled": True,
            "variant": "dust",
            "style": "glow",
            "spawnArea": "full",
            "travelMode": "fall",
            "spawnMode": "always",
            "speed": 0.7,
            "lifetimeSec": 6.0,
            "size": 5.5,
            "opacity": 0.4,
            "reactivity": 0.15,
            "audioMotionMode": "travel",
            "audioTravelBoost": 0.7,
            "maxCount": 480,
            "spawnRate": 180,
            "smoothing": 0.68,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.1,
            "sizeJitter": 0.6,
            "drift": 0.5,
            "swirl": 0.18,
            "reactStrength": 0.28,
            "glow": 0.1,
            "color": "#8a8680",
            "reactColor": "#c4bfb6",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "confetti",
        "Confetti",
        {
            "enabled": True,
            "variant": "classic",
            "style": "dot",
            "spawnArea": "screenCenter",
            "travelMode": "burst",
            "spawnMode": "reactiveOnly",
            "speed": 4.2,
            "lifetimeSec": 2.2,
            "size": 4.5,
            "opacity": 0.95,
            "reactivity": 0.5,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.3,
            "maxCount": 600,
            "spawnRate": 420,
            "smoothing": 0.18,
            "spawnTrigger": "kick",
            "spawnThreshold": 0.05,
            "sizeJitter": 0.7,
            "drift": 0.35,
            "swirl": 0.4,
            "reactStrength": 0.85,
            "glow": 0.15,
            "color": "#ff5c8a",
            "reactColor": "#ffe566",
            "colorMode": "palette",
            "paletteColors": ["#ff5c8a", "#ffe566", "#5ce1ff", "#a3ff7a"],
        },
    ),
    (
        "leaves",
        "Leaves",
        {
            "enabled": True,
            "variant": "classic",
            "style": "dot",
            "spawnArea": "full",
            "travelMode": "fall",
            "spawnMode": "always",
            "speed": 1.0,
            "lifetimeSec": 5.5,
            "size": 7.0,
            "opacity": 0.75,
            "reactivity": 0.2,
            "audioMotionMode": "travel",
            "audioTravelBoost": 0.9,
            "maxCount": 260,
            "spawnRate": 70,
            "smoothing": 0.6,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.1,
            "sizeJitter": 0.55,
            "drift": 0.65,
            "swirl": 0.45,
            "reactStrength": 0.35,
            "glow": 0.05,
            "color": "#c45c26",
            "reactColor": "#e8a05c",
            "colorMode": "palette",
            "paletteColors": ["#c45c26", "#7a9e3e", "#d4a017", "#8b4513"],
        },
    ),
    (
        "sparkles",
        "Sparkles",
        {
            "enabled": True,
            "variant": "classic",
            "style": "spark",
            "spawnArea": "centerRing",
            "travelMode": "burst",
            "spawnMode": "reactiveOnly",
            "speed": 5.8,
            "lifetimeSec": 0.85,
            "size": 3.6,
            "opacity": 1.0,
            "reactivity": 0.65,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.15,
            "maxCount": 640,
            "spawnRate": 700,
            "smoothing": 0.06,
            "spawnTrigger": "kick",
            "spawnThreshold": 0.03,
            "sizeJitter": 0.35,
            "drift": 0.06,
            "swirl": 0.1,
            "reactStrength": 1.0,
            "glow": 0.75,
            "color": "#ffffff",
            "reactColor": "#7ef9ff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    # Fill → 20 (proposed names locked as shipped)
    (
        "embers",
        "Embers",
        {
            "enabled": True,
            "variant": "classic",
            "style": "spark",
            "spawnArea": "bottom",
            "travelMode": "rise",
            "spawnMode": "reactiveOnly",
            "speed": 2.4,
            "lifetimeSec": 1.65,
            "size": 5.4,
            "opacity": 0.88,
            "reactivity": 0.38,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.0,
            "maxCount": 420,
            "spawnRate": 280,
            "smoothing": 0.16,
            "spawnTrigger": "both",
            "spawnThreshold": 0.04,
            "sizeJitter": 0.52,
            "drift": 0.32,
            "swirl": 0.06,
            "reactStrength": 0.72,
            "glow": 0.5,
            "color": "#ff9a3c",
            "reactColor": "#fff0c8",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "petals",
        "Petals",
        {
            "enabled": True,
            "variant": "classic",
            "style": "dot",
            "spawnArea": "full",
            "travelMode": "fall",
            "spawnMode": "always",
            "speed": 0.95,
            "lifetimeSec": 5.8,
            "size": 6.8,
            "opacity": 0.72,
            "reactivity": 0.18,
            "audioMotionMode": "travel",
            "audioTravelBoost": 0.85,
            "maxCount": 320,
            "spawnRate": 90,
            "smoothing": 0.66,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.1,
            "sizeJitter": 0.5,
            "drift": 0.7,
            "swirl": 0.38,
            "reactStrength": 0.32,
            "glow": 0.1,
            "color": "#ff8fab",
            "reactColor": "#ffd6e0",
            "colorMode": "palette",
            "paletteColors": ["#ff8fab", "#ffc2d1", "#fb6f92", "#ffffff"],
        },
    ),
    (
        "glitter",
        "Glitter",
        {
            "enabled": True,
            "variant": "classic",
            "style": "spark",
            "spawnArea": "screenRandom",
            "travelMode": "random",
            "spawnMode": "always",
            "speed": 1.6,
            "lifetimeSec": 2.4,
            "size": 2.8,
            "opacity": 0.95,
            "reactivity": 0.4,
            "audioMotionMode": "sizePulse",
            "audioTravelBoost": 0.9,
            "maxCount": 800,
            "spawnRate": 380,
            "smoothing": 0.25,
            "spawnTrigger": "both",
            "spawnThreshold": 0.06,
            "sizeJitter": 0.4,
            "drift": 0.2,
            "swirl": 0.15,
            "reactStrength": 0.7,
            "glow": 0.65,
            "color": "#f5e6a3",
            "reactColor": "#ffffff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "smoke_rings",
        "Smoke Rings",
        {
            "enabled": True,
            "variant": "soap",
            "style": "ring",
            "spawnArea": "centerRing",
            "travelMode": "rise",
            "spawnMode": "always",
            "speed": 0.8,
            "lifetimeSec": 6.2,
            "size": 16.0,
            "opacity": 0.32,
            "reactivity": 0.2,
            "audioMotionMode": "both",
            "audioTravelBoost": 0.85,
            "maxCount": 180,
            "spawnRate": 55,
            "smoothing": 0.78,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.1,
            "sizeJitter": 0.45,
            "drift": 0.28,
            "swirl": 0.55,
            "reactStrength": 0.4,
            "glow": 0.2,
            "color": "#9aa3b2",
            "reactColor": "#d5dbe6",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "energy_orbs",
        "Energy Orbs",
        {
            "enabled": True,
            "variant": "bokeh",
            "style": "bokeh",
            "spawnArea": "centerRing",
            "travelMode": "spawnFlow",
            "spawnMode": "reactiveOnly",
            "speed": 2.0,
            "lifetimeSec": 2.8,
            "size": 11.0,
            "opacity": 0.7,
            "reactivity": 0.5,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.2,
            "maxCount": 240,
            "spawnRate": 200,
            "smoothing": 0.35,
            "spawnTrigger": "kick",
            "spawnThreshold": 0.04,
            "sizeJitter": 0.4,
            "drift": 0.18,
            "swirl": 0.42,
            "reactStrength": 0.88,
            "glow": 0.8,
            "color": "#5eead4",
            "reactColor": "#ffffff",
            "colorMode": "palette",
            "paletteColors": ["#5eead4", "#38bdf8", "#a78bfa", "#ffffff"],
        },
    ),
    (
        "pixel_dust",
        "Pixel Dust",
        {
            "enabled": True,
            "variant": "classic",
            "style": "dot",
            "spawnArea": "full",
            "travelMode": "spawnFlow",
            "spawnMode": "always",
            "speed": 1.35,
            "lifetimeSec": 3.5,
            "size": 2.0,
            "opacity": 0.8,
            "reactivity": 0.3,
            "audioMotionMode": "both",
            "audioTravelBoost": 1.0,
            "maxCount": 1000,
            "spawnRate": 450,
            "smoothing": 0.4,
            "spawnTrigger": "both",
            "spawnThreshold": 0.07,
            "sizeJitter": 0.2,
            "drift": 0.25,
            "swirl": 0.1,
            "reactStrength": 0.55,
            "glow": 0.05,
            "color": "#94a3b8",
            "reactColor": "#e2e8f0",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
    (
        "feather_drift",
        "Feather Drift",
        {
            "enabled": True,
            "variant": "dust",
            "style": "glow",
            "spawnArea": "full",
            "travelMode": "fall",
            "spawnMode": "always",
            "speed": 0.55,
            "lifetimeSec": 8.0,
            "size": 9.5,
            "opacity": 0.42,
            "reactivity": 0.14,
            "audioMotionMode": "travel",
            "audioTravelBoost": 0.7,
            "maxCount": 220,
            "spawnRate": 45,
            "smoothing": 0.82,
            "spawnTrigger": "bass",
            "spawnThreshold": 0.12,
            "sizeJitter": 0.75,
            "drift": 0.8,
            "swirl": 0.28,
            "reactStrength": 0.25,
            "glow": 0.18,
            "color": "#f8f1e7",
            "reactColor": "#ffffff",
            "colorMode": "solid",
            "paletteColors": [],
        },
    ),
)

PARTICLE_TYPE_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {"id": row[0], "label": row[1], "recipe": dict(row[2])} for row in _TYPE_ROWS
)
PARTICLE_TYPE_IDS: frozenset[str] = frozenset(item["id"] for item in PARTICLE_TYPE_CATALOG)
PARTICLE_TYPE_COUNT = len(PARTICLE_TYPE_CATALOG)
assert PARTICLE_TYPE_COUNT == 20, PARTICLE_TYPE_COUNT

GPU_PARTICLE_VARIANTS: frozenset[str] = frozenset({"classic", "bokeh", "soap", "dust"})

_TYPE_BY_ID: dict[str, dict[str, Any]] = {item["id"]: item for item in PARTICLE_TYPE_CATALOG}

_TYPE_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in PARTICLE_TYPE_CATALOG},
    **{item["label"].lower(): item["id"] for item in PARTICLE_TYPE_CATALOG},
    "smoke rings": "smoke_rings",
    "energy orbs": "energy_orbs",
    "pixel dust": "pixel_dust",
    "feather drift": "feather_drift",
    "dust field": "dust",
    "floating dust": "dust",
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
    if spaced in _TYPE_ALIASES:
        return _TYPE_ALIASES[spaced]
    if raw in _TYPE_ALIASES:
        return _TYPE_ALIASES[raw]
    return None


def get_particle_type(type_id: str | None) -> dict[str, Any] | None:
    key = normalize_particle_type_id(type_id)
    if not key:
        return None
    item = _TYPE_BY_ID[key]
    return {"id": item["id"], "label": item["label"], "recipe": deepcopy(item["recipe"])}


def gpu_variant_for_particle_type(type_id: str | None) -> str | None:
    item = get_particle_type(type_id)
    if item is None:
        return None
    variant = str(item["recipe"].get("variant") or "").strip().lower()
    return variant if variant in GPU_PARTICLE_VARIANTS else None


def _paint_particles_settings(
    current: dict[str, Any],
    recipe: dict[str, Any],
    *,
    preserve_colors: bool,
) -> dict[str, Any]:
    out = dict(current)
    for key, value in recipe.items():
        if key in _COLOR_KEYS and preserve_colors and key in current and current.get(key) not in (None, "", []):
            continue
        if key in _TYPE_RECIPE_KEYS or key in _COLOR_KEYS:
            out[key] = deepcopy(value) if isinstance(value, (dict, list)) else value
    out["enabled"] = True
    return out


def apply_particle_type_to_template(template: dict[str, Any], type_id: str) -> dict[str, Any]:
    """Apply particle type recipe without changing behavior axis."""
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    particle = get_particle_type(type_id)
    if particle is None:
        raise ValueError(f"unknown particle type: {type_id!r}")

    ensure_composition_on_template(template)
    prev_behavior = template["composition"]["particles"]["behavior"]
    prev_palette = template["composition"].get("colorPalette")
    recipe = particle["recipe"]

    current = template.get("particlesSettings")
    if not isinstance(current, dict):
        current = {}
    preserve_colors = bool(
        (isinstance(current.get("color"), str) and current.get("color"))
        or (isinstance(current.get("paletteColors"), list) and current.get("paletteColors"))
    )
    next_settings = _paint_particles_settings(current, recipe, preserve_colors=preserve_colors)
    # Keep Layer 4 behavior stub on legacy bag when already present.
    if prev_behavior and prev_behavior != NONE:
        next_settings["behavior"] = prev_behavior
    elif "behavior" in current:
        next_settings["behavior"] = current.get("behavior")
    template["particlesSettings"] = next_settings

    scene = apply_particles_axes(
        template.get("composition"),
        type=particle["id"],
        behavior=prev_behavior if prev_behavior else NONE,
    )
    if not prev_behavior or prev_behavior == NONE:
        scene["particles"]["behavior"] = NONE
    if prev_palette:
        scene["colorPalette"] = prev_palette
    template["composition"] = normalize_composition_scene(scene)
    return template
