"""Atmosphere catalog (15) — weather/fog/sky layer (Session B: not particles/lighting/post)."""

from __future__ import annotations

from typing import Any

_ATMOSPHERE_ROWS: tuple[tuple[str, str], ...] = (
    ("fog", "Fog"),
    ("mist", "Mist"),
    ("rain", "Rain"),
    ("snow", "Snow"),
    ("storm", "Storm"),
    ("stars", "Stars"),
    ("clouds", "Clouds"),
    ("dust", "Dust"),
    ("smoke", "Smoke"),
    ("nebula", "Nebula"),
    ("aurora", "Aurora"),
    ("haze", "Haze"),
    ("heatwave", "Heatwave"),
    ("underwater", "Underwater"),
    ("void", "Void"),
)

ATMOSPHERE_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _ATMOSPHERE_ROWS
)
ATMOSPHERE_IDS: frozenset[str] = frozenset(item["id"] for item in ATMOSPHERE_CATALOG)
ATMOSPHERE_COUNT = len(ATMOSPHERE_CATALOG)
assert ATMOSPHERE_COUNT == 15, ATMOSPHERE_COUNT

_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in ATMOSPHERE_CATALOG},
    **{item["label"].lower(): item["id"] for item in ATMOSPHERE_CATALOG},
}


def list_atmosphere_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in ATMOSPHERE_CATALOG)


def normalize_atmosphere_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw or raw == "none":
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in ATMOSPHERE_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None
