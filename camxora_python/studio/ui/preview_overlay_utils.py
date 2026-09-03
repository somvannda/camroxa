"""Shared paint helpers for transparent preview drag overlays."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

# CAMXORA brand purple — matches timeline clip handles and design tokens.
OVERLAY_ACCENT = QColor("#7466F1")
OVERLAY_ACCENT_LIGHT = QColor("#A259FF")
OVERLAY_GHOST_FILL = QColor(116, 102, 241, 40)


def prepare_transparent_overlay(widget: QWidget) -> None:
    """Overlay stacks on PreviewCanvas; parent repaint restores pixels under cleared areas."""
    widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
    widget.setAutoFillBackground(False)


def repaint_parent_region(overlay: QWidget, region: QRect) -> None:
    """Ask the preview canvas to redraw composited content under ``region``."""
    if region.isEmpty():
        return
    parent = overlay.parentWidget()
    if parent is None:
        return
    top_left = overlay.mapTo(parent, region.topLeft())
    parent.repaint(QRect(top_left, region.size()))


def begin_overlay_frame(painter: QPainter, clip: QRect) -> None:
    """Clear only the invalidated clip, then draw the current selection."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(clip)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    painter.fillRect(clip, Qt.GlobalColor.transparent)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


def drag_dirty_rect(prev: QRect | None, current: QRect, *, margin: int = 6) -> QRect:
    """Union of previous and current overlay bounds (with handle margin)."""
    pad = margin
    dirty = current.adjusted(-pad, -pad, pad, pad)
    if prev is not None and not prev.isEmpty():
        dirty = dirty.united(prev.adjusted(-pad, -pad, pad, pad))
    return dirty
