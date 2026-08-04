"""Rounded frameless window chrome — outer shell only; inner cards stay unchanged."""

from __future__ import annotations

import sys
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QApplication, QWidget

# Subtle outer radius — matches studio cards (4–6px) without looking bubbly.
WINDOW_CORNER_RADIUS = 8


def center_window_on_screen(window: QWidget) -> None:
    """Center *window* on its current (or primary) screen's available work area."""
    if window.isMaximized() or window.isFullScreen():
        return

    screen = window.screen()
    if screen is None:
        app = QApplication.instance()
        if app is not None:
            screen = app.primaryScreen()
    if screen is None:
        return

    geo = screen.availableGeometry()
    frame = window.frameGeometry()
    width = frame.width() if frame.width() > 0 else window.width()
    height = frame.height() if frame.height() > 0 else window.height()
    x = geo.x() + max(0, (geo.width() - width) // 2)
    y = geo.y() + max(0, (geo.height() - height) // 2)
    window.move(x, y)


def configure_rounded_window(window: QWidget, *, radius: int = WINDOW_CORNER_RADIUS) -> None:
    """Enable rounded corners on the top-level frameless window.

    ``WA_TranslucentBackground`` is required so the OS composites the area
    outside the rounded mask as clear (otherwise square corners show a black
    or theme-colored box). The opaque studio fill is painted by
    ``QWidget#window_surface`` (see ``deep_blue.py``), not by QMainWindow.

    Side effect: ``QOpenGLWidget`` FBO alpha becomes real window transparency.
    Preview must keep destination alpha at 1 (REQ-P0 Alpha_Lock). Do not clear
    this attribute without an alternate rounded-chrome strategy (REQ-P3.2).
    """
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
