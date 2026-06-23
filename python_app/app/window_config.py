"""Single source of truth for the application's main window size and maximize behaviour.

Both top-level app windows (the login/onboarding window and the main window)
must use the exact same fixed size. Import ``apply_fixed_window_size`` and call
it instead of hardcoding ``resize``/``setFixedSize`` values per window.

``toggle_maximize`` provides cross-platform maximize/restore that behaves like
the native macOS green zoom button (fills available screen area) and also works
natively on Windows.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QWidget

# The one and only app window size. Change it here and every window follows.
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080


def apply_fixed_window_size(window: QWidget) -> None:
    """Resize *window* to the app's standard size, capped to the screen work area, and center it.

    Uses ``resize`` (not ``setFixedSize``) so that the window can still be
    maximized on all platforms.  Capping to the available geometry keeps the
    frameless window from spilling off-screen on smaller displays.
    """
    screen = window.screen()
    if screen is not None:
        geo = screen.availableGeometry()
        w = min(WINDOW_WIDTH, geo.width())
        h = min(WINDOW_HEIGHT, geo.height())
        window.resize(w, h)
        window.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)
    else:
        window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)


def toggle_maximize(window: QWidget) -> None:
    """Toggle between maximized and normal window state.

    On macOS, frameless windows ignore ``showMaximized()`` so we manually
    expand to the screen's available geometry (matching the native green
    zoom-button behaviour).  On Windows, ``showMaximized`` / ``showNormal``
    work natively and are used directly.
    """
    if window.isMaximized():
        _restore_window(window)
    else:
        _maximize_window(window)


def _maximize_window(window: QWidget) -> None:
    """Maximize *window* to fill the available screen area."""
    if sys.platform == "darwin":
        # Save pre-maximize geometry so we can restore it later.
        geo = window.geometry()
        window.setProperty("_pre_maximize_geo", geo)
        screen = window.screen()
        if screen is not None:
            ag = screen.availableGeometry()
            window.setGeometry(ag)
        else:
            window.showMaximized()
    else:
        window.showMaximized()


def _restore_window(window: QWidget) -> None:
    """Restore *window* to its size/position before it was maximized."""
    if sys.platform == "darwin":
        prev = window.property("_pre_maximize_geo")
        if isinstance(prev, QRect) and prev.isValid():
            window.setGeometry(prev)
        else:
            window.showNormal()
        window.setProperty("_pre_maximize_geo", None)
    else:
        window.showNormal()
