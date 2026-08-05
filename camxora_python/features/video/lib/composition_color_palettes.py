"""Composition Engine P2 — named color palettes (Layer 6).

Stable palette ids for ``composition.colorPalette``. Applying a palette writes
colors across Spectrum layers, Particles, Lighting, and Text/Overlay fields
without inventing one-off hex in new presets.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from features.video.lib.composition_scene_contract import (
    ensure_composition_on_template,
    normalize_composition_scene,
)

# (id, label, stops[4], accent)
# Canonical 12 first, then fill slots → 20.
_PALETTE_ROWS: tuple[tuple[str, str, tuple[str, str, str, str], str], ...] = (
    ("cyberpunk", "Cyberpunk", ("#ff00ff", "#00ffff", "#7c3aed", "#f472b6"), "#22d3ee"),
    ("synthwave", "Synthwave", ("#ff6ec7", "#ff8a5c", "#7c3aed", "#38bdf8"), "#f0abfc"),
    ("festival", "Festival", ("#fbbf24", "#f472b6", "#22d3ee", "#a3e635"), "#fb923c"),
    ("edm", "EDM", ("#22d3ee", "#a78bfa", "#f472b6", "#34d399"), "#67e8f9"),
    ("dubstep", "Dubstep", ("#84cc16", "#a3e635", "#f97316", "#ef4444"), "#bef264"),
    ("future_bass", "Future Bass", ("#c084fc", "#67e8f9", "#f9a8d4", "#818cf8"), "#e9d5ff"),
    ("sunset", "Sunset", ("#fb7185", "#fb923c", "#fbbf24", "#f472b6"), "#fdba74"),
    ("aurora", "Aurora", ("#34d399", "#22d3ee", "#818cf8", "#a78bfa"), "#6ee7b7"),
    ("galaxy", "Galaxy", ("#818cf8", "#c084fc", "#e879f9", "#38bdf8"), "#ddd6fe"),
    ("fire", "Fire", ("#ef4444", "#f97316", "#fbbf24", "#fb7185"), "#fecaca"),
    ("ocean", "Ocean", ("#0ea5e9", "#22d3ee", "#2dd4bf", "#38bdf8"), "#7dd3fc"),
    ("monochrome", "Monochrome", ("#f8fafc", "#cbd5e1", "#94a3b8", "#64748b"), "#e2e8f0"),
    # Fill slots → target 20
    ("midnight", "Midnight", ("#1e3a8a", "#312e81", "#6366f1", "#22d3ee"), "#93c5fd"),
    ("neon_pink", "Neon Pink", ("#ff4fd8", "#f472b6", "#fb7185", "#a78bfa"), "#fda4af"),
    ("tropical", "Tropical", ("#2dd4bf", "#34d399", "#fbbf24", "#fb7185"), "#5eead4"),
    ("industrial", "Industrial", ("#94a3b8", "#64748b", "#f97316", "#e2e8f0"), "#cbd5e1"),
    ("candy", "Candy", ("#fb7185", "#f9a8d4", "#a5b4fc", "#67e8f9"), "#fda4af"),
    ("blood_moon", "Blood Moon", ("#7f1d1d", "#b91c1c", "#f97316", "#fbbf24"), "#fca5a5"),
    ("arctic", "Arctic", ("#e0f2fe", "#7dd3fc", "#38bdf8", "#a5b4fc"), "#bae6fd"),
    ("gold_rush", "Gold Rush", ("#fbbf24", "#f59e0b", "#eab308", "#fde68a"), "#fcd34d"),
)

COLOR_PALETTE_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {
        "id": row[0],
        "label": row[1],
        "stops": list(row[2]),
        "accent": row[3],
        "solid": row[2][0],
    }
    for row in _PALETTE_ROWS
)

COLOR_PALETTE_IDS: frozenset[str] = frozenset(item["id"] for item in COLOR_PALETTE_CATALOG)
COLOR_PALETTE_COUNT = len(COLOR_PALETTE_CATALOG)
assert COLOR_PALETTE_COUNT == 20, COLOR_PALETTE_COUNT

_PALETTE_BY_ID: dict[str, dict[str, Any]] = {item["id"]: item for item in COLOR_PALETTE_CATALOG}

# Alias human / legacy labels → id
_PALETTE_ALIASES: dict[str, str] = {
    "cyberpunk": "cyberpunk",
    "synthwave": "synthwave",
    "festival": "festival",
    "edm": "edm",
    "dubstep": "dubstep",
    "future bass": "future_bass",
    "future-bass": "future_bass",
    "future_bass": "future_bass",
    "sunset": "sunset",
    "aurora": "aurora",
    "galaxy": "galaxy",
    "fire": "fire",
    "ocean": "ocean",
    "monochrome": "monochrome",
    "midnight": "midnight",
    "neon pink": "neon_pink",
    "neon-pink": "neon_pink",
    "neon_pink": "neon_pink",
    "tropical": "tropical",
    "industrial": "industrial",
    "candy": "candy",
    "blood moon": "blood_moon",
    "blood-moon": "blood_moon",
    "blood_moon": "blood_moon",
    "arctic": "arctic",
    "gold rush": "gold_rush",
    "gold-rush": "gold_rush",
    "gold_rush": "gold_rush",
}


def list_color_palette_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in COLOR_PALETTE_CATALOG)


def normalize_color_palette_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace("_", " ")
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in COLOR_PALETTE_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _PALETTE_ALIASES:
        return _PALETTE_ALIASES[spaced]
    if compact.replace("_", " ") in _PALETTE_ALIASES:
        return _PALETTE_ALIASES[compact.replace("_", " ")]
    return None


def get_color_palette(palette_id: str | None) -> dict[str, Any] | None:
    key = normalize_color_palette_id(palette_id)
    if not key:
        return None
    return deepcopy(_PALETTE_BY_ID[key])


def apply_color_palette_to_template(template: dict[str, Any], palette_id: str) -> dict[str, Any]:
    """Apply palette colors across domains; set ``composition.colorPalette``.

    Mutates and returns ``template``.
    """
    if not isinstance(template, dict):
        raise TypeError("template must be a dict")
    palette = get_color_palette(palette_id)
    if palette is None:
        raise ValueError(f"unknown color palette: {palette_id!r}")

    stops: list[str] = list(palette["stops"])
    solid = str(palette["solid"])
    accent = str(palette["accent"])

    # Spectrum layers (+ multi-instance stacks)
    layers = template.get("layers")
    if isinstance(layers, list):
        template["layers"] = [_paint_layer_color(layer, stops, solid) for layer in layers]

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
                cloned["layers"] = [_paint_layer_color(layer, stops, solid) for layer in inst_layers]
            next_instances.append(cloned)
        template["spectrumInstances"] = next_instances

    # Particles
    particles = template.get("particlesSettings")
    if not isinstance(particles, dict):
        particles = {}
        template["particlesSettings"] = particles
    particles["color"] = solid
    particles["reactColor"] = accent
    particles["colorMode"] = "palette"
    particles["paletteColors"] = list(stops)

    # Lighting / lightning
    lightning = template.get("lightningLayers")
    if isinstance(lightning, list):
        template["lightningLayers"] = [
            _paint_lightning_layer(layer, stops, solid) for layer in lightning
        ]

    # Text overlays (typography)
    overlays = template.get("textOverlays")
    if isinstance(overlays, list):
        template["textOverlays"] = [_paint_text_overlay(item, solid, accent) for item in overlays]

    for key in ("albumText", "titleText"):
        block = template.get(key)
        if isinstance(block, dict):
            template[key] = _paint_text_domain(block, solid, accent, stops)

    # Overlay domain (frames / stickers) — color fields when present
    overlay_settings = template.get("overlaySettings")
    if isinstance(overlay_settings, dict):
        items = overlay_settings.get("items")
        if isinstance(items, list):
            overlay_settings["items"] = [
                _paint_overlay_item(item, solid, accent) for item in items
            ]

    # Composition id
    ensure_composition_on_template(template)
    scene = normalize_composition_scene(template.get("composition"))
    scene["colorPalette"] = palette["id"]
    template["composition"] = scene
    return template


def _paint_layer_color(layer: Any, stops: list[str], solid: str) -> Any:
    if not isinstance(layer, dict):
        return layer
    out = deepcopy(layer)
    out["color"] = {
        "mode": "gradient",
        "solidColor": solid,
        "gradientColors": list(stops),
        "gradientDirection": "left-to-right",
    }
    return out


def _paint_lightning_layer(layer: Any, stops: list[str], solid: str) -> Any:
    if not isinstance(layer, dict):
        return layer
    out = deepcopy(layer)
    out["color"] = {
        "mode": "gradient",
        "solidColor": solid,
        "gradientColors": list(stops[:3]) if len(stops) >= 2 else [solid, stops[-1] if stops else solid],
    }
    return out


def _paint_text_overlay(item: Any, solid: str, accent: str) -> Any:
    if not isinstance(item, dict):
        return item
    out = deepcopy(item)
    out["color"] = solid
    if "strokeColor" in out:
        out["strokeColor"] = accent
    return out


def _paint_text_domain(block: dict[str, Any], solid: str, accent: str, stops: list[str]) -> dict[str, Any]:
    out = deepcopy(block)
    style = out.get("style") if isinstance(out.get("style"), dict) else {}
    style = deepcopy(style)
    style["fillMode"] = "gradient"
    style["gradientColors"] = list(stops[:3]) if len(stops) >= 2 else [solid, accent]
    style["gradientDirection"] = style.get("gradientDirection") or "vertical"
    if "glowColor" in style or style.get("glow"):
        style["glowColor"] = accent
    out["style"] = style
    if "listColor" in out:
        out["listColor"] = solid
    if "listActiveColor" in out:
        out["listActiveColor"] = accent
    return out


def _paint_overlay_item(item: Any, solid: str, accent: str) -> Any:
    if not isinstance(item, dict):
        return item
    out = deepcopy(item)
    if "color" in out or out.get("fill"):
        out["color"] = solid
    if "accentColor" in out:
        out["accentColor"] = accent
    if "strokeColor" in out:
        out["strokeColor"] = accent
    return out
