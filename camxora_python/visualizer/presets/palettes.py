"""Color palette catalog (20)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

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

_BY_ID = {item["id"]: item for item in COLOR_PALETTE_CATALOG}
_ALIASES = {
    **{item["id"]: item["id"] for item in COLOR_PALETTE_CATALOG},
    **{item["label"].lower(): item["id"] for item in COLOR_PALETTE_CATALOG},
    "future bass": "future_bass",
    "neon pink": "neon_pink",
    "blood moon": "blood_moon",
    "gold rush": "gold_rush",
}


def list_color_palette_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in COLOR_PALETTE_CATALOG)


def normalize_color_palette_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in COLOR_PALETTE_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None


def get_palette(palette_id: str | None) -> dict[str, Any] | None:
    key = normalize_color_palette_id(palette_id)
    if not key:
        return None
    return deepcopy(_BY_ID[key])
