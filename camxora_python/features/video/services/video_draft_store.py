"""Local video workspace draft persistence — port of videoWorkspaceDraftStore.ts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from features.video.lib.video_template_draft import clone_layer_records
from shared.lib.app_paths import get_video_draft_store_dir


def _draft_path(template_id: str) -> Path:
    normalized = str(template_id or "").strip()
    return get_video_draft_store_dir() / f"{normalized}.json"


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


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
    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        return None

    path = _draft_path(normalized_id)
    if not path.is_file():
        return None

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

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
    }


def write_video_workspace_draft_snapshot(
    template_id: str,
    *,
    template_name: str,
    draft: dict[str, Any],
    layers: list[dict[str, Any]],
) -> None:
    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        return

    path = _draft_path(normalized_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "templateName": template_name,
        "draft": draft,
        "layers": clone_layer_records(layers),
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def clear_video_workspace_draft_snapshot(template_id: str) -> None:
    normalized_id = str(template_id or "").strip()
    if not normalized_id:
        return
    path = _draft_path(normalized_id)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            return
