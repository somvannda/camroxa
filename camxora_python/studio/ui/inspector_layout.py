"""Shared spacing tokens and helpers for the clip inspector panel."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout

# Vertical rhythm (px)
PAGE_TOP = 12
SECTION_GAP = 14
FIELD_GAP = 8
FIELD_ROW_GAP = 6
HEADER_SUBTITLE_GAP = 4
TAB_TIER_GAP = 4
SLIDER_BLOCK_GAP = 10

# Horizontal alignment for label / value rows
SPIN_LABEL_WIDTH = 96
SPIN_INPUT_WIDTH = 76
MUSIC_PANEL_H_PADDING = 5
# Right inspector — minimum wide enough for playlist settings (sliders, row-element labels).
INSPECTOR_PANEL_MIN_WIDTH = 400
INSPECTOR_PANEL_DEFAULT_WIDTH = 400
# Scroll content cap — keeps form rows compact when the user widens the panel.
INSPECTOR_CONTENT_MAX_WIDTH = 368
FORM_LABEL_WIDTH = 112
# Reserve space so scrollable inspector content is not clipped by the vertical bar.
SCROLLBAR_GUTTER = 14
PLAYLIST_SETTINGS_H_INSET = 8

# Shape picker grid
SHAPE_GRID_H_SPACING = 8
SHAPE_GRID_V_SPACING = 6


def apply_page_layout(layout: QVBoxLayout) -> None:
    layout.setContentsMargins(0, PAGE_TOP, 0, 0)
    layout.setSpacing(0)


def apply_scroll_page_layout(layout: QVBoxLayout) -> None:
    """Page layout for QScrollArea contents — keeps a right gutter for the scrollbar."""
    layout.setContentsMargins(0, PAGE_TOP, SCROLLBAR_GUTTER, 12)
    layout.setSpacing(0)


def apply_playlist_settings_layout(layout: QVBoxLayout) -> None:
    """Scroll page for Playlist → Settings — inset content so borders don't clip."""
    layout.setContentsMargins(
        PLAYLIST_SETTINGS_H_INSET,
        PAGE_TOP,
        SCROLLBAR_GUTTER + PLAYLIST_SETTINGS_H_INSET,
        12,
    )
    layout.setSpacing(0)


def apply_music_page_layout(layout: QVBoxLayout) -> None:
    layout.setContentsMargins(MUSIC_PANEL_H_PADDING, PAGE_TOP, MUSIC_PANEL_H_PADDING, 0)
    layout.setSpacing(0)


def add_section_spacer(layout: QVBoxLayout) -> None:
    layout.addSpacing(SECTION_GAP)


def configure_field_row(row: QHBoxLayout) -> None:
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(FIELD_GAP)


def configure_slider_column(col: QVBoxLayout) -> None:
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(FIELD_ROW_GAP)


def configure_shape_grid(grid: QGridLayout) -> None:
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(SHAPE_GRID_H_SPACING)
    grid.setVerticalSpacing(SHAPE_GRID_V_SPACING)
