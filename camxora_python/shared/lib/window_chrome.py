"""Rounded frameless window chrome — outer shell only; inner cards stay unchanged."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainterPath, QRegion

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

# Subtle outer radius — matches studio cards (4–6px) without looking bubbly.
WINDOW_CORNER_RADIUS = 8


def configure_rounded_window(window: QWidget, *, radius: int = WINDOW_CORNER_RADIUS) -> None:
    """Enable rounded corners on the top-level frameless window."""
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    sync_rounded_window_shape(window, radius=radius)


def sync_rounded_window_shape(window: QWidget, *, radius: int = WINDOW_CORNER_RADIUS) -> None:
    """Update window mask and outer surface styling for the current window state."""
    surface = window.centralWidget()
    if window.isMaximized() or window.isFullScreen():
        window.clearMask()
        if sys.platform == "win32":
            _set_windows_corner_preference(window, round_corners=False)
        _set_surface_rounded(surface, rounded=False, radius=radius)
        return

    path = QPainterPath()
    path.addRoundedRect(QRectF(window.rect()), radius, radius)
    window.setMask(QRegion(path.toFillPolygon().toPolygon()))
    if sys.platform == "win32":
        _set_windows_corner_preference(window, round_corners=True)
    _set_surface_rounded(surface, rounded=True, radius=radius)


def _set_surface_rounded(surface: QWidget | None, *, rounded: bool, radius: int) -> None:
    if surface is None:
        return
    surface.setProperty("roundedCorners", rounded)
    surface.setProperty("cornerRadius", radius if rounded else 0)
    surface.style().unpolish(surface)
    surface.style().polish(surface)


def _set_windows_corner_preference(window: QWidget, *, round_corners: bool) -> None:
    try:
        import ctypes

        hwnd = int(window.winId())
        if hwnd == 0:
            return
        preference = 2 if round_corners else 1
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            33,
            ctypes.byref(ctypes.c_int(preference)),
            ctypes.sizeof(ctypes.c_int),
        )
    except Exception:
        return
