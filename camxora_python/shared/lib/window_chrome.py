"""Rounded frameless window chrome — outer shell only; inner cards stay unchanged.

Windowed rounding uses Windows DWM corner preference + QSS border-radius on the
opaque ``#window_surface``. We deliberately do **not** use ``setMask()`` or
``WA_TranslucentBackground`` on the main shell: that combo breaks mouse
hit-testing on some Windows DPI setups (clicks land offset from painted
controls). Maximized mode already cleared the mask historically; windowed mode
now matches that hit-test-safe path.

Note: older builds kept translucency for rounded corner compositing and relied
on preview Alpha_Lock (REQ-P0) so ``QOpenGLWidget`` FBO alpha would not show
the desktop. 1.2.0 switches to an opaque HWND (REQ-P3.2) which also removes
that transparency side effect for the shell.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
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
    """Enable rounded corners on the top-level frameless window (hit-test safe)."""
    # Opaque HWND: avoid layered/translucent hit-test bugs under fractional DPI.
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    window.clearMask()
    sync_rounded_window_shape(window, radius=radius)


def sync_rounded_window_shape(window: QWidget, *, radius: int = WINDOW_CORNER_RADIUS) -> None:
    """Update DWM rounding + outer surface styling for the current window state."""
    # Always clear any legacy region mask so clicks match painted controls.
    window.clearMask()
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

    surface = window.centralWidget()
    if window.isMaximized() or window.isFullScreen():
        if sys.platform == "win32":
            _set_windows_corner_preference(window, round_corners=False)
        _set_surface_rounded(surface, rounded=False, radius=radius)
        return

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
        # DWMWA_WINDOW_CORNER_PREFERENCE (33): DONOTROUND=1, ROUND=2 (Windows 11+).
        preference = 2 if round_corners else 1
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            33,
            ctypes.byref(ctypes.c_int(preference)),
            ctypes.sizeof(ctypes.c_int),
        )
    except Exception:
        return
