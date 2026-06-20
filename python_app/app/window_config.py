"""Single source of truth for the application's main window size.

Both top-level app windows (the login/onboarding window and the main window)
must use the exact same fixed size. Import ``apply_fixed_window_size`` and call
it instead of hardcoding ``resize``/``setFixedSize`` values per window.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

# The one and only app window size. Change it here and every window follows.
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080


def apply_fixed_window_size(window: QWidget) -> None:
    """Pin *window* to the app's fixed size, capped to the screen work area, and center it.

    Capping to the available geometry keeps the frameless window from spilling
    off-screen on displays smaller than ``WINDOW_WIDTH`` x ``WINDOW_HEIGHT``.
    """
    screen = window.screen()
    if screen is not None:
        geo = screen.availableGeometry()
        w = min(WINDOW_WIDTH, geo.width())
        h = min(WINDOW_HEIGHT, geo.height())
        window.setFixedSize(w, h)
        window.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)
    else:
        window.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
