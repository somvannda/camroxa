"""Background motion catalog (10) — orthogonal to atmosphere."""

from __future__ import annotations

from typing import Any

_MOTION_ROWS: tuple[tuple[str, str], ...] = (
    ("static", "Static"),
    ("slow_zoom", "Slow Zoom"),
    ("ken_burns", "Ken Burns"),
    ("orbit", "Orbit"),
    ("parallax", "Parallax"),
    ("ripple", "Ripple"),
    ("energy_wave", "Energy Wave"),
    ("floating", "Floating"),
    ("rotate", "Rotate"),
    ("warp", "Warp"),
)

BACKGROUND_MOTION_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _MOTION_ROWS
)
BACKGROUND_MOTION_IDS: frozenset[str] = frozenset(item["id"] for item in BACKGROUND_MOTION_CATALOG)
BACKGROUND_MOTION_COUNT = len(BACKGROUND_MOTION_CATALOG)
assert BACKGROUND_MOTION_COUNT == 10, BACKGROUND_MOTION_COUNT

_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in BACKGROUND_MOTION_CATALOG},
    **{item["label"].lower(): item["id"] for item in BACKGROUND_MOTION_CATALOG},
    "slow zoom": "slow_zoom",
    "ken burns": "ken_burns",
    "energy wave": "energy_wave",
    "none": "static",
}


def list_background_motion_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in BACKGROUND_MOTION_CATALOG)


def normalize_background_motion_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in BACKGROUND_MOTION_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None
