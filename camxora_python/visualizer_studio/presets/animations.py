"""Animation behavior catalog (12) — shared Layer 4 ids."""

from __future__ import annotations

from typing import Any

_BEHAVIOR_ROWS: tuple[tuple[str, str], ...] = (
    ("pulse", "Pulse"),
    ("bounce", "Bounce"),
    ("rotate", "Rotate"),
    ("expand", "Expand"),
    ("contract", "Contract"),
    ("ripple", "Ripple"),
    ("wave", "Wave"),
    ("twist", "Twist"),
    ("elastic", "Elastic"),
    ("fade", "Fade"),
    ("flash", "Flash"),
    ("breathing", "Breathing"),
)

ANIMATION_BEHAVIOR_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _BEHAVIOR_ROWS
)
ANIMATION_BEHAVIOR_IDS: frozenset[str] = frozenset(item["id"] for item in ANIMATION_BEHAVIOR_CATALOG)
ANIMATION_BEHAVIOR_COUNT = len(ANIMATION_BEHAVIOR_CATALOG)
assert ANIMATION_BEHAVIOR_COUNT == 12, ANIMATION_BEHAVIOR_COUNT

ANIMATION_TARGETS: tuple[str, ...] = ("spectrum", "logo", "overlay", "particles")

_ALIASES = {
    **{item["id"]: item["id"] for item in ANIMATION_BEHAVIOR_CATALOG},
    **{item["label"].lower(): item["id"] for item in ANIMATION_BEHAVIOR_CATALOG},
}


def list_animation_behavior_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in ANIMATION_BEHAVIOR_CATALOG)


def normalize_animation_behavior_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in ANIMATION_BEHAVIOR_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None
