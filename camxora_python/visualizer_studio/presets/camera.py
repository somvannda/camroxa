"""Camera behavior catalog (15) — scene-level, not spectrum."""

from __future__ import annotations

from typing import Any

_CAMERA_ROWS: tuple[tuple[str, str], ...] = (
    ("zoom", "Zoom"),
    ("pan", "Pan"),
    ("orbit", "Orbit"),
    ("rotate", "Rotate"),
    ("shake", "Shake"),
    ("tilt", "Tilt"),
    ("dolly", "Dolly"),
    ("roll", "Roll"),
    ("focus_pull", "Focus Pull"),
    ("parallax", "Parallax"),
    ("handheld", "Handheld"),
    ("crane", "Crane"),
    ("whip_pan", "Whip Pan"),
    ("punch_in", "Punch In"),
    ("drift", "Drift"),
)

CAMERA_BEHAVIOR_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _CAMERA_ROWS
)
CAMERA_BEHAVIOR_IDS: frozenset[str] = frozenset(item["id"] for item in CAMERA_BEHAVIOR_CATALOG)
CAMERA_BEHAVIOR_COUNT = len(CAMERA_BEHAVIOR_CATALOG)
assert CAMERA_BEHAVIOR_COUNT == 15, CAMERA_BEHAVIOR_COUNT

_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in CAMERA_BEHAVIOR_CATALOG},
    **{item["label"].lower(): item["id"] for item in CAMERA_BEHAVIOR_CATALOG},
    "focus pull": "focus_pull",
    "whip pan": "whip_pan",
    "punch in": "punch_in",
}


def list_camera_behavior_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in CAMERA_BEHAVIOR_CATALOG)


def normalize_camera_behavior_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw or raw == "none":
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in CAMERA_BEHAVIOR_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None
