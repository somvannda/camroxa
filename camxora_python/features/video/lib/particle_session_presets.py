"""Persistent particle preset overrides (local JSON + factory recipes)."""

from __future__ import annotations

from typing import Any

from features.video.lib.domain_preset_store import (
    clear_domain_preset_override,
    get_domain_preset_override,
    has_domain_preset_override,
    save_domain_preset_override,
)
from features.video.lib.particle_settings import (
    PARTICLE_MOTION_PRESET_FIELD_KEYS,
    PARTICLE_MOTION_PRESETS,
    build_particle_motion_preset_patch,
)
from features.video.lib.spectrum_style_registry import PACK_PRESET_PREFIX
from features.video.lib.template_draft_domains import pick_particles_draft_slice

_DOMAIN = "particles"
_BUILTIN_PRESET_IDS = frozenset(preset_id for preset_id, _label in PARTICLE_MOTION_PRESETS)


def clear_session_particle_presets() -> None:
    """Compatibility alias — clears all particle overrides on disk."""
    from features.video.lib.domain_preset_store import clear_all_domain_preset_overrides

    clear_all_domain_preset_overrides(_DOMAIN)


def has_session_particle_preset(preset_id: str) -> bool:
    key = str(preset_id or "").strip()
    if not key or key.startswith(PACK_PRESET_PREFIX) or key not in _BUILTIN_PRESET_IDS:
        return False
    return has_domain_preset_override(_DOMAIN, key)


def get_session_particle_preset_patch(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if not key or key.startswith(PACK_PRESET_PREFIX) or key not in _BUILTIN_PRESET_IDS:
        return None
    stored = get_domain_preset_override(_DOMAIN, key)
    return dict(stored) if isinstance(stored, dict) else None


def resolve_particle_preset_patch(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    if not key or key.startswith(PACK_PRESET_PREFIX) or key not in _BUILTIN_PRESET_IDS:
        return None
    session = get_session_particle_preset_patch(key)
    if session is not None:
        return session
    return build_particle_motion_preset_patch(key)


def capture_session_particle_preset(preset_id: str, draft: dict[str, Any]) -> None:
    key = str(preset_id or "").strip()
    if not key or key.startswith(PACK_PRESET_PREFIX) or key not in _BUILTIN_PRESET_IDS:
        return
    factory = build_particle_motion_preset_patch(key) or {}
    slice_data = pick_particles_draft_slice(draft)
    stored = dict(factory)
    for field in PARTICLE_MOTION_PRESET_FIELD_KEYS:
        value = slice_data.get(field)
        if value is not None:
            stored[field] = value
    save_domain_preset_override(_DOMAIN, key, stored)


def restore_particle_preset_to_factory(preset_id: str) -> dict[str, Any] | None:
    """Clear local override and return factory patch."""
    key = str(preset_id or "").strip()
    if not key or key not in _BUILTIN_PRESET_IDS:
        return None
    clear_domain_preset_override(_DOMAIN, key)
    return build_particle_motion_preset_patch(key)


def particle_patch_touches_preset_fields(patch: dict[str, Any]) -> bool:
    return any(key in PARTICLE_MOTION_PRESET_FIELD_KEYS for key in patch.keys())
