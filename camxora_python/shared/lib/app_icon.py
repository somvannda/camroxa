"""Application branding icon helpers for window chrome and taskbar."""

from __future__ import annotations

from PySide6.QtGui import QIcon, QPixmap

from shared.icons.chrome_assets import APP_LOGO_SVG
from shared.lib.resource_paths import get_resource_path

_APP_ICON_CANDIDATES = ("app-icon.ico", "app.ico")


def load_app_icon() -> QIcon:
    """Load the Camxora app icon for the window and taskbar.

    Prefers ``resources/app-icon.ico``. Falls back to the embedded brand SVG so a
    missing package asset never leaves the default Windows placeholder icon.
    """
    for name in _APP_ICON_CANDIDATES:
        ico_path = get_resource_path(name)
        if ico_path.is_file():
            icon = QIcon(str(ico_path))
            if not icon.isNull():
                return icon

    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QPainter
    from PySide6.QtSvg import QSvgRenderer

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(APP_LOGO_SVG.encode("utf-8")))
        if renderer.isValid():
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            icon.addPixmap(pixmap)
    return icon
