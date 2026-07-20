"""Application branding icon helpers for window chrome and taskbar."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from shared.icons.chrome_assets import APP_LOGO_SVG
from shared.lib.resource_paths import get_resource_path

# Keep in sync with installer shortcut AppUserModelID (Camxora.iss [Icons]).
APP_USER_MODEL_ID = "Camxora.DesktopStudio"

_APP_ICON_CANDIDATES = ("app-icon.ico", "app.ico")
_cached_qt_icon: QIcon | None = None
_cached_small_hicon: int | None = None
_cached_big_hicon: int | None = None


def resolve_app_icon_path() -> Path | None:
    """Return the packaged ``.ico`` path when present."""
    for name in _APP_ICON_CANDIDATES:
        ico_path = get_resource_path(name)
        if ico_path.is_file():
            return ico_path
    return None


def load_app_icon() -> QIcon:
    """Load the Camxora app icon for the window and taskbar.

    Prefers ``resources/app-icon.ico``. Falls back to the embedded brand SVG so a
    missing package asset never leaves the default Windows placeholder icon.
    """
    global _cached_qt_icon
    if _cached_qt_icon is not None and not _cached_qt_icon.isNull():
        return _cached_qt_icon

    ico_path = resolve_app_icon_path()
    if ico_path is not None:
        icon = QIcon(str(ico_path))
        if not icon.isNull():
            _cached_qt_icon = icon
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
    _cached_qt_icon = icon
    return icon


def _load_native_hicons(ico_path: Path) -> tuple[int, int]:
    """Load and cache SMALL/BIG HICONs for repeated WM_SETICON calls."""
    global _cached_small_hicon, _cached_big_hicon
    if _cached_small_hicon and _cached_big_hicon:
        return _cached_small_hicon, _cached_big_hicon

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    LR_LOADFROMFILE = 0x0010
    IMAGE_ICON = 1

    LoadImageW = user32.LoadImageW
    LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    LoadImageW.restype = wintypes.HANDLE

    path = str(ico_path)
    small = int(LoadImageW(None, path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE) or 0)
    big = int(LoadImageW(None, path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE) or 0)
    if small and big:
        _cached_small_hicon = small
        _cached_big_hicon = big
    return small, big


def _apply_native_windows_icon(window: QWidget, ico_path: Path) -> None:
    """Stamp SMALL/BIG icons on the HWND so the taskbar prefers the .ico over a live preview."""
    try:
        import ctypes
    except Exception:
        return

    hwnd = int(window.winId())
    if hwnd == 0:
        return

    small, big = _load_native_hicons(ico_path)
    if not small and not big:
        return

    user32 = ctypes.windll.user32
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    if small:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
    if big:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)


def apply_app_window_icon(window: QWidget | None = None) -> QIcon:
    """Apply the brand icon to the process and optionally a concrete window.

    Call at startup, after show, and again when GPU export/preview can steal the
    taskbar surface (GLFW creates an offscreen HWND that Windows may promote).
    """
    icon = load_app_icon()
    app = QApplication.instance()
    if app is not None:
        app.setWindowIcon(icon)
    target = window
    if target is None and app is not None:
        active = app.activeWindow()
        if isinstance(active, QWidget):
            target = active
        else:
            widgets = app.topLevelWidgets()
            target = widgets[0] if widgets else None
    if target is not None:
        target.setWindowIcon(icon)
        if sys.platform == "win32":
            ico_path = resolve_app_icon_path()
            if ico_path is not None:
                _apply_native_windows_icon(target, ico_path)
    return icon


def refresh_app_window_icon(widget: QWidget | None = None) -> None:
    """Re-stamp branding on the given widget's top-level window (safe no-op off Windows)."""
    if widget is None:
        apply_app_window_icon()
        return
    top = widget.window()
    apply_app_window_icon(top if isinstance(top, QWidget) else widget)
