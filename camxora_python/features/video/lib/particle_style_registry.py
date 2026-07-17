"""Particle preset registry — unified built-in + marketplace dropdown."""

from __future__ import annotations

from typing import Any

from features.video.lib.particle_settings import (
    PARTICLE_MOTION_PRESET_FIELD_KEYS,
    PARTICLE_MOTION_PRESETS,
)
from features.video.lib.particle_session_presets import resolve_particle_preset_patch
from features.video.lib.spectrum_style_registry import (
    PACK_PRESET_PREFIX,
    encode_pack_preset_key,
    parse_pack_preset_key,
)

__all__ = (
    "PACK_PRESET_PREFIX",
    "build_unified_particle_preset_options",
    "encode_pack_preset_key",
    "parse_pack_preset_key",
    "resolve_active_particle_preset_key",
    "build_builtin_particle_preset_patch",
    "is_builtin_particle_preset_key",
)


def build_unified_particle_preset_options(
    catalog_items: list[dict[str, Any]] | None = None,
) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = list(PARTICLE_MOTION_PRESETS)
    for item in catalog_items or []:
        if item.get("domain") != "particles":
            continue
        if item.get("status") not in {"ready", "available"}:
            continue
        pack_id = str(item.get("packId") or "").strip()
        version = str(item.get("version") or "").strip()
        name = str(item.get("name") or pack_id).strip()
        if not pack_id or not version:
            continue
        options.append(
            (
                encode_pack_preset_key(pack_id, version),
                f"{name} ({version})",
            )
        )
    return tuple(options)


def resolve_active_particle_preset_key(draft: dict[str, Any]) -> str | None:
    for preset_id, _label in PARTICLE_MOTION_PRESETS:
        patch = resolve_particle_preset_patch(preset_id)
        if not patch:
            continue
        if all(draft.get(key) == patch.get(key) for key in PARTICLE_MOTION_PRESET_FIELD_KEYS):
            return preset_id
    return None


def build_builtin_particle_preset_patch(preset_key: str) -> dict[str, Any] | None:
    """Built-in preset patch, preferring in-session customized values when present."""
    normalized = str(preset_key or "").strip()
    if not normalized or normalized.startswith(PACK_PRESET_PREFIX):
        return None
    return resolve_particle_preset_patch(normalized)


def is_builtin_particle_preset_key(preset_key: str | None) -> bool:
    key = str(preset_key or "").strip()
    if not key or key.startswith(PACK_PRESET_PREFIX):
        return False
    return any(key == preset_id for preset_id, _label in PARTICLE_MOTION_PRESETS)
