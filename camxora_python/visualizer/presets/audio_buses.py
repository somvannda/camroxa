"""Audio reaction buses (8) — Session C: Vocals/Melody/Snare are v1 FFT heuristics."""

from __future__ import annotations

from typing import Any

_BUS_ROWS: tuple[tuple[str, str, bool], ...] = (
    ("bass", "Bass", False),
    ("treble", "Treble", False),
    ("vocals", "Vocals", True),
    ("beat", "Beat", False),
    ("melody", "Melody", True),
    ("kick", "Kick", False),
    ("snare", "Snare", True),
    ("overall_loudness", "Overall Loudness", False),
)

AUDIO_BUS_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {"id": row[0], "label": row[1], "heuristic": row[2]} for row in _BUS_ROWS
)
AUDIO_BUS_IDS: frozenset[str] = frozenset(item["id"] for item in AUDIO_BUS_CATALOG)
AUDIO_BUS_COUNT = len(AUDIO_BUS_CATALOG)
assert AUDIO_BUS_COUNT == 8, AUDIO_BUS_COUNT

HEURISTIC_AUDIO_BUS_IDS: frozenset[str] = frozenset(
    item["id"] for item in AUDIO_BUS_CATALOG if item["heuristic"]
)

# Mapping targets (architecture tree objects that can be driven by a bus).
AUDIO_MAPPING_TARGETS: tuple[tuple[str, str], ...] = (
    ("lighting", "Lighting trigger"),
    ("particles", "Particles emit"),
    ("camera", "Camera"),
    ("logo", "Logo pulse"),
)

_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in AUDIO_BUS_CATALOG},
    **{str(item["label"]).lower(): item["id"] for item in AUDIO_BUS_CATALOG},
    "overall loudness": "overall_loudness",
    "loudness": "overall_loudness",
}


def list_audio_bus_options() -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            item["id"],
            f"{item['label']} (heuristic)" if item["heuristic"] else item["label"],
        )
        for item in AUDIO_BUS_CATALOG
    )


def list_audio_mapping_target_options() -> tuple[tuple[str, str], ...]:
    return AUDIO_MAPPING_TARGETS


def normalize_audio_bus_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw or raw == "none":
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in AUDIO_BUS_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None


def is_heuristic_bus(bus_id: str | None) -> bool:
    return bool(bus_id) and bus_id in HEURISTIC_AUDIO_BUS_IDS
