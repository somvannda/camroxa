"""Tests for text overlay editor helpers."""

from __future__ import annotations

from features.video.lib.text_editor import (
    add_text_overlay,
    apply_text_anchor_alignment,
    apply_text_case,
    apply_text_preset_to_overlays,
    duplicate_text_overlay,
    get_text_anchor_alignment,
)


def test_apply_text_case_modes() -> None:
    assert apply_text_case("hello world", "upper") == "HELLO WORLD"
    assert apply_text_case("HELLO", "lower") == "hello"
    assert apply_text_case("hello world", "title") == "Hello World"


def test_apply_text_anchor_alignment_preserves_vertical() -> None:
    assert apply_text_anchor_alignment("top-center", "left") == "top-left"
    assert get_text_anchor_alignment("top-left") == "left"


def test_add_and_duplicate_text_overlay() -> None:
    overlays, index = add_text_overlay([])
    assert len(overlays) == 1
    assert index == 0
    next_overlays, next_index = duplicate_text_overlay(overlays, 0)
    assert len(next_overlays) == 2
    assert next_index == 1


def test_neon_outline_preset_applies_to_selected_layer() -> None:
    overlays, index = add_text_overlay([])
    next_overlays, _ = apply_text_preset_to_overlays(overlays, "neon_outline", selected_index=index)
    assert next_overlays[0]["strokeColor"] == "#ff4fd8"
    assert next_overlays[0]["animation"] == "pop"
