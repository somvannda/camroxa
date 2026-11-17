"""Normalize per-kind image source modes (prompt_only / category / personal_reference)."""

from __future__ import annotations

from typing import Any

from platform_api.models.enums import ImageKind

SOURCE_MODE_PROMPT_ONLY = "prompt_only"
SOURCE_MODE_CATEGORY = "category"
SOURCE_MODE_PERSONAL_REFERENCE = "personal_reference"

PROMPT_SOURCE_CUSTOM = "custom"
PROMPT_SOURCE_ADMIN_LIBRARY = "admin_library"

_BG_EMPTY_PROMPT = (
    "Background: Add a background prompt, or switch Background source to Category / User reference."
)
_TH_EMPTY_PROMPT = (
    "Thumbnail: Add a thumbnail prompt, or switch Thumbnail source to Category / User reference."
)
_PERSONAL_NOT_READY = (
    "{kind}: User reference images from the portal are not available yet. "
    "Switch to Category or Prompt only for now."
)


def normalize_image_kind_source_mode(
    settings: dict[str, Any] | None,
    kind: ImageKind | str,
) -> str:
    """Return ``prompt_only``, ``category``, or ``personal_reference`` for the kind.

    Keys: ``imageBackgroundSourceMode`` / ``imageThumbnailSourceMode``.
    Legacy: ``backgroundSourceMode=prompt`` maps background → prompt_only.
    """
    data = settings if isinstance(settings, dict) else {}
    kind_value = str(getattr(kind, "value", kind) or "").strip().lower()
    dual_key = (
        "imageBackgroundSourceMode"
        if kind_value == "background"
        else "imageThumbnailSourceMode"
    )
    raw = str(data.get(dual_key) or "").strip().lower()
    if not raw:
        legacy = str(data.get("backgroundSourceMode") or "").strip().lower()
        if kind_value == "background" and legacy in {"prompt", "prompt_only"}:
            return SOURCE_MODE_PROMPT_ONLY
        return SOURCE_MODE_CATEGORY

    if raw in {"prompt", "prompt_only"}:
        return SOURCE_MODE_PROMPT_ONLY
    if raw in {"personal", "personal_reference", "user_reference"}:
        return SOURCE_MODE_PERSONAL_REFERENCE
    return SOURCE_MODE_CATEGORY


def is_prompt_only_source(settings: dict[str, Any] | None, kind: ImageKind | str) -> bool:
    return normalize_image_kind_source_mode(settings, kind) == SOURCE_MODE_PROMPT_ONLY


def is_personal_reference_source(settings: dict[str, Any] | None, kind: ImageKind | str) -> bool:
    return normalize_image_kind_source_mode(settings, kind) == SOURCE_MODE_PERSONAL_REFERENCE


def normalize_prompt_source(settings: dict[str, Any] | None, kind: ImageKind | str) -> str:
    """Return ``custom`` or ``admin_library`` for the kind.

    Keys: ``imageBackgroundPromptSource`` / ``imageThumbnailPromptSource``.
    Unknown values fall back to ``custom`` so old clients keep their prompt.
    """
    data = settings if isinstance(settings, dict) else {}
    kind_value = str(getattr(kind, "value", kind) or "").strip().lower()
    key = (
        "imageBackgroundPromptSource"
        if kind_value == "background"
        else "imageThumbnailPromptSource"
    )
    raw = str(data.get(key) or "").strip().lower()
    if raw in {"library", "admin", "admin_library", "prompt_library"}:
        return PROMPT_SOURCE_ADMIN_LIBRARY
    return PROMPT_SOURCE_CUSTOM


def is_admin_prompt_source(settings: dict[str, Any] | None, kind: ImageKind | str) -> bool:
    return normalize_prompt_source(settings, kind) == PROMPT_SOURCE_ADMIN_LIBRARY


def empty_prompt_library_message(kind: ImageKind | str) -> str:
    kind_value = str(getattr(kind, "value", kind) or "").strip().lower()
    label = "Thumbnail" if kind_value == "thumbnail" else "Background"
    return (
        f"{label}: No active admin prompt styles are available. "
        "Ask an admin to add one in Admin → Image Prompts, or switch the prompt source "
        "back to My prompt."
    )



def empty_prompt_error_message(kind: ImageKind | str) -> str:
    kind_value = str(getattr(kind, "value", kind) or "").strip().lower()
    if kind_value == "thumbnail":
        return _TH_EMPTY_PROMPT
    return _BG_EMPTY_PROMPT


def personal_reference_not_ready_message(kind: ImageKind | str) -> str:
    kind_value = str(getattr(kind, "value", kind) or "").strip().lower()
    label = "Thumbnail" if kind_value == "thumbnail" else "Background"
    return _PERSONAL_NOT_READY.format(kind=label)
