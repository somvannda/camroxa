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


# Contextual Tuning UI — which shared expert knobs apply to each motion, + labels.
# Keys: speed | amplitude | zoom | warp (document: motionSpeed/Amplitude/Zoom/Warp).
_MOTION_TUNING_UI: dict[str, dict[str, str]] = {
    "static": {},
    "slow_zoom": {"speed": "Speed", "zoom": "Zoom"},
    "ken_burns": {"speed": "Speed", "amplitude": "Pan strength", "zoom": "Zoom"},
    "orbit": {"speed": "Speed", "amplitude": "Amplitude", "zoom": "Zoom"},
    "parallax": {"speed": "Speed", "amplitude": "Amplitude", "zoom": "Zoom"},
    "ripple": {
        "speed": "Speed",
        "amplitude": "Amplitude",
        "zoom": "Zoom",
        "warp": "Warp",
    },
    "energy_wave": {
        "speed": "Speed",
        "amplitude": "Amplitude",
        "zoom": "Zoom",
        "warp": "Warp",
    },
    "floating": {"speed": "Speed", "amplitude": "Amplitude", "zoom": "Zoom"},
    "rotate": {"speed": "Speed", "amplitude": "Amplitude", "zoom": "Zoom"},
    "warp": {
        "speed": "Speed",
        "amplitude": "Amplitude",
        "zoom": "Zoom",
        "warp": "Warp",
    },
}


def background_motion_tuning_ui(motion_id: Any) -> dict[str, str]:
    """Return ``{knob_key: label}`` for the active motion (empty for static)."""
    mid = normalize_background_motion_id(motion_id) or "static"
    return dict(_MOTION_TUNING_UI.get(mid) or {})
