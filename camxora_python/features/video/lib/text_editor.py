"""Text overlay editor helpers — port of useTextEditor.ts."""

from __future__ import annotations

import copy
import re
from typing import Any, Literal

from features.video.lib.text_overlay_presets import (
    build_neon_brush_stack_overlays,
    build_text_preset_style,
    clone_text_overlays,
)
from features.video.lib.video_template_draft import build_default_text_overlay_draft

TextAlignment = Literal["left", "center", "right"]
TextCaseMode = Literal["upper", "lower", "title"]


def get_text_anchor_alignment(anchor: str) -> TextAlignment:
    normalized = str(anchor or "")
    if normalized.endswith("left"):
        return "left"
    if normalized.endswith("right"):
        return "right"
    return "center"


def apply_text_case(text: str, mode: TextCaseMode) -> str:
    if mode == "upper":
        return text.upper()
    if mode == "lower":
        return text.lower()
    return re.sub(
        r"\w\S*",
        lambda match: match.group(0)[0].upper() + match.group(0)[1:].lower(),
        text,
    )


def apply_text_anchor_alignment(anchor: str, alignment: TextAlignment) -> str:
    current = str(anchor or "center")
    if current.startswith("top"):
        vertical = "top"
    elif current.startswith("bottom"):
        vertical = "bottom"
    else:
        vertical = "center"

    if vertical == "center":
        if alignment == "center":
            return "center"
        if alignment == "left":
            return "bottom-left"
        return "bottom-right"
    return f"{vertical}-{alignment}"


def resolve_selected_text_overlay_index(overlays: list[dict[str, Any]], selected_key: str) -> int:
    if not overlays:
        return 0
    try:
        raw = int(selected_key)
    except (TypeError, ValueError):
        raw = 0
    return max(0, min(len(overlays) - 1, raw))


def update_text_overlay_at(
    overlays: list[dict[str, Any]],
    index: int,
    next_overlay: dict[str, Any],
) -> list[dict[str, Any]]:
    return [next_overlay if item_index == index else item for item_index, item in enumerate(overlays)]


def add_text_overlay(overlays: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    next_overlays = [*overlays, build_default_text_overlay_draft()]
    return next_overlays, len(next_overlays) - 1


def duplicate_text_overlay(overlays: list[dict[str, Any]], index: int) -> tuple[list[dict[str, Any]], int]:
    overlay = overlays[index]
    next_overlays = [
        *overlays[: index + 1],
        copy.deepcopy(overlay),
        *overlays[index + 1 :],
    ]
    return next_overlays, index + 1


def delete_text_overlay(overlays: list[dict[str, Any]], index: int) -> tuple[list[dict[str, Any]], int]:
    next_overlays = [item for item_index, item in enumerate(overlays) if item_index != index]
    next_index = max(0, min(index, len(next_overlays) - 1)) if next_overlays else 0
    return next_overlays, next_index


def move_text_overlay(
    overlays: list[dict[str, Any]],
    index: int,
    direction: int,
) -> tuple[list[dict[str, Any]], int] | None:
    next_index = index + direction
    if next_index < 0 or next_index >= len(overlays):
        return None
    next_overlays = overlays.copy()
    next_overlays[index], next_overlays[next_index] = next_overlays[next_index], next_overlays[index]
    return next_overlays, next_index


def apply_text_preset_to_overlays(
    overlays: list[dict[str, Any]],
    preset: str,
    *,
    selected_index: int,
) -> tuple[list[dict[str, Any]], int]:
    if preset == "neon_brush_stack":
        next_overlays = [*overlays, *build_neon_brush_stack_overlays()]
        return next_overlays, len(next_overlays) - 1

    style = build_text_preset_style(preset)
    if not style:
        return overlays, selected_index

    if overlays and 0 <= selected_index < len(overlays):
        selected = overlays[selected_index]
        next_overlays = update_text_overlay_at(
            overlays,
            selected_index,
            {**selected, **style},
        )
        return next_overlays, selected_index

    next_overlay = {**build_default_text_overlay_draft(), "enabled": True, **style}
    next_overlays = [*overlays, next_overlay]
    return next_overlays, len(next_overlays) - 1
