"""Shared selected-state colors for inspector controls (purple + white text)."""

from __future__ import annotations

from studio.app.theme import PALETTE

SELECTED_TEXT = "#ffffff"
SELECTED_HOVER = "#8a70ff"


def selected_chip_background(*, hover: bool = False) -> str:
    return SELECTED_HOVER if hover else PALETTE.accent


def animation_card_style(*, selected: bool) -> tuple[str, str]:
    """Return (frame_stylesheet, name_label_stylesheet)."""
    if selected:
        frame = (
            f"QFrame#AnimationPresetCard {{ background-color: {PALETTE.accent};"
            f" border: 1px solid {PALETTE.accent}; border-radius: 10px; }}"
        )
        name = "color: #ffffff; font-size: 10px; background: transparent;"
        return frame, name
    frame = (
        f"QFrame#AnimationPresetCard {{ background-color: {PALETTE.panel2};"
        f" border: 1px solid {PALETTE.border}; border-radius: 10px; }}"
    )
    name = f"color: {PALETTE.text_dim}; font-size: 10px; background: transparent;"
    return frame, name


def inspector_tab_style(*, checked: bool) -> str:
    if checked:
        return (
            f"QPushButton#InspectorTabButton {{ background-color: {PALETTE.accent};"
            f" border: none; border-radius: 6px; padding: 7px 12px;"
            f" font-size: 12px; font-weight: 600; color: #ffffff; }}"
            f"QPushButton#InspectorTabButton:hover {{ background-color: {SELECTED_HOVER};"
            f" color: #ffffff; }}"
        )
    return (
        f"QPushButton#InspectorTabButton {{ background: transparent; border: none;"
        f" border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;"
        f" color: {PALETTE.text_dimmer}; }}"
        f"QPushButton#InspectorTabButton:hover {{ color: {PALETTE.text};"
        f" background: {PALETTE.panel2}; }}"
    )
