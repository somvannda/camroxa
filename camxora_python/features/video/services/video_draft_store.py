"""In-memory video workspace draft store (session only).

Unsaved draft edits stay while the app is open so switching templates mid-session
can restore each draft. Closing the app discards them. Explicit Save writes the
catalog in ``video-templates.json``; restart loads the last saved template only.

Legacy on-disk ``video-drafts/*.json`` files are ignored and removed once.
"""

from __future__ import annotations

from typing import Any

from features.video.lib.video_template_draft import clone_layer_records
from shared.lib.app_paths import get_video_draft_store_dir

_MEMORY: dict[str, dict[str, Any]] = {}
_DISK_CLEANED = False


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _cleanup_legacy_disk_drafts() -> None:
    global _DISK_CLEANED
    if _DISK_CLEANED:
        return
    _DISK_CLEANED = True
    root = get_video_draft_store_dir()
    if not root.is_dir():
        return
    try:
        for path in root.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                continue
    except OSError:
        return


def _apply_legacy_spectrum_fields(draft: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    legacy_keys = (
        "style",
        "spectrumEnabled",
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
    if not any(key in parsed for key in legacy_keys):
        return draft

    next_draft = dict(draft)
    for key in legacy_keys:
        if key in parsed:
            next_draft[key] = parsed[key]
    return next_draft


def read_video_workspace_draft_snapshot(
    template_id: str,
    persisted_draft: dict[str, Any],
    persisted_template_name: str,
) -> dict[str, Any] | None:
    _cleanup_legacy_disk_drafts()
    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        return None

    parsed = _MEMORY.get(normalized_id)
    if not _is_record(parsed):
        return None

    if _is_record(parsed.get("draft")):
        draft = {**persisted_draft, **parsed["draft"]}
    else:
        draft = _apply_legacy_spectrum_fields(persisted_draft, parsed)

    template_name = parsed.get("templateName")
    if not isinstance(template_name, str):
        template_name = persisted_template_name

    return {
        "templateName": template_name,
        "draft": draft,
        "layers": clone_layer_records(parsed.get("layers")),
        "lightningLayers": clone_layer_records(parsed.get("lightningLayers")),
    }


def write_video_workspace_draft_snapshot(
    template_id: str,
    *,
    template_name: str,
    draft: dict[str, Any],
    layers: list[dict[str, Any]],
    lightning_layers: list[dict[str, Any]] | None = None,
) -> None:
    _cleanup_legacy_disk_drafts()
    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        return
    _MEMORY[normalized_id] = {
        "templateName": template_name,
        "draft": dict(draft),
        "layers": clone_layer_records(layers),
        "lightningLayers": clone_layer_records(lightning_layers or []),
    }


def clear_video_workspace_draft_snapshot(template_id: str) -> None:
    _cleanup_legacy_disk_drafts()
    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        return
    _MEMORY.pop(normalized_id, None)


def reset_video_draft_memory_for_tests() -> None:
    """Test helper: wipe in-memory drafts and allow disk cleanup again."""
    global _DISK_CLEANED
    _MEMORY.clear()
    _DISK_CLEANED = False
