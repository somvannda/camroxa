"""Session spectrum preset overrides (in-memory + factory recipes)."""

from __future__ import annotations

from typing import Any

from features.video.lib.domain_preset_store import (
    clear_domain_preset_override,
    get_domain_preset_override,
    has_domain_preset_override,
    save_domain_preset_override,
)
from features.video.lib.spectrum_style_registry import (
    PACK_PRESET_PREFIX,
    SPECTRUM_PRESET_OPTIONS,
    STACKED_SPECTRUM_PRESET_OPTIONS,
    normalize_spectrum_preset_key_for_apply,
)
from features.video.lib.template_draft_domains import pick_spectrum_draft_slice
from features.video.lib.video_template_draft import clone_layer_records

_DOMAIN = "spectrum"
_BUILTIN_STYLE_IDS = frozenset(preset_id for preset_id, _label in SPECTRUM_PRESET_OPTIONS)
_STACKED_IDS = frozenset(preset_id for preset_id, _label in STACKED_SPECTRUM_PRESET_OPTIONS)
_ALL_SESSION_IDS = _BUILTIN_STYLE_IDS | _STACKED_IDS

SPECTRUM_SESSION_DRAFT_KEYS: tuple[str, ...] = (
    "spectrumEnabled",
    "style",
    "audioInputGain",
    "audioBarHeight",
    "audioBandContrast",
    "audioTransientFocus",
    "audioKickImpact",
    "audioBassEmphasis",
    "audioTrebleShimmer",
    "audioPeakHoldBlend",
    "audioMotionSmoothing",
    "flyingGlowWingMotionSpeed",
    "flyingGlowWingRelease",
    "spectrumAttachToLogo",
    "spectrumLogoGap",
    "anchor",
    "positionX",
    "positionY",
)


def clear_session_spectrum_presets() -> None:
    from features.video.lib.domain_preset_store import clear_all_domain_preset_overrides

    clear_all_domain_preset_overrides(_DOMAIN)


def has_session_spectrum_preset(preset_id: str) -> bool:
    key = _normalize_session_key(preset_id)
    return bool(key and has_domain_preset_override(_DOMAIN, key))


def is_session_spectrum_preset_key(preset_key: str | None) -> bool:
    return _normalize_session_key(str(preset_key or "")) is not None


def get_session_spectrum_preset(preset_id: str) -> dict[str, Any] | None:
    key = _normalize_session_key(preset_id)
    if not key:
        return None
    stored = get_domain_preset_override(_DOMAIN, key)
    if not isinstance(stored, dict):
        return None
    draft = stored.get("draft")
    layers = stored.get("layers")
    if not isinstance(draft, dict) or not isinstance(layers, list):
        return None
    return {"draft": dict(draft), "layers": clone_layer_records(layers)}


def capture_session_spectrum_preset(
    preset_id: str,
    draft: dict[str, Any],
    layers: list[dict[str, Any]],
) -> None:
    key = _normalize_session_key(preset_id)
    if not key:
        return
    slice_data = pick_spectrum_draft_slice(draft)
    stored_draft = {field: slice_data.get(field) for field in SPECTRUM_SESSION_DRAFT_KEYS}
    if key in _BUILTIN_STYLE_IDS:
        stored_draft["style"] = key
    save_domain_preset_override(
        _DOMAIN,
        key,
        {"draft": stored_draft, "layers": clone_layer_records(layers)},
    )


def restore_spectrum_preset_to_factory(preset_id: str) -> bool:
    key = _normalize_session_key(preset_id)
    if not key:
        return False
    return clear_domain_preset_override(_DOMAIN, key)


def spectrum_patch_touches_preset_fields(patch: dict[str, Any]) -> bool:
    return any(key in SPECTRUM_SESSION_DRAFT_KEYS for key in patch.keys())


def _normalize_session_key(preset_id: str) -> str | None:
    raw = str(preset_id or "").strip()
    if not raw or raw.startswith(PACK_PRESET_PREFIX):
        return None
    if raw in _STACKED_IDS:
        return raw
    if raw in _BUILTIN_STYLE_IDS:
        return raw
    normalized = normalize_spectrum_preset_key_for_apply(raw)
    if normalized in _STACKED_IDS:
        return normalized
    if normalized in _BUILTIN_STYLE_IDS:
        return normalized
    return None
