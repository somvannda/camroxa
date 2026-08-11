"""Video-local audio mapping helpers (authoring axes only; classic GPU ignores these)."""

from __future__ import annotations

from typing import Any

from features.video.lib.composition_audio_buses import AUDIO_BUS_IDS, normalize_audio_bus_id
from features.video.lib.composition_scene_contract import NONE

MAPPING_TARGETS: tuple[str, ...] = ("spectrum", "lighting", "particles", "camera", "logo")


def normalize_audio_mapping(raw: Any) -> dict[str, str]:
    out: dict[str, str] = {key: NONE for key in MAPPING_TARGETS}
    if not isinstance(raw, dict):
        return out
    for target in MAPPING_TARGETS:
        bus = normalize_audio_bus_id(raw.get(target))
        out[target] = bus or NONE
    return out


def bus_is_known(bus_id: str | None) -> bool:
    return bool(bus_id) and bus_id in AUDIO_BUS_IDS
