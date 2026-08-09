"""Lucide-style stroke icons as tinted SVG pixmaps for Qt widgets."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from shared.constants.navigation import ShellRouteKey

# Icon paths from lucide-static (ISC) — viewBox 0 0 24 24
_LUCIDE_PATHS: dict[str, tuple[str, ...]] = {
    "gauge": (
        '<path d="m12 14 4-4"/>',
        '<path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    ),
    "user-round": (
        '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>',
        '<circle cx="12" cy="7" r="4"/>',
    ),
    "workflow": (
        '<rect width="8" height="8" x="3" y="3" rx="2"/>',
        '<path d="M7 11v4a2 2 0 0 0 2 2h4"/>',
        '<rect width="8" height="8" x="13" y="13" rx="2"/>',
    ),
    "activity": (
        '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    ),
    "music-4": (
        '<path d="M9 18V5l12-2v13"/>',
        '<circle cx="6" cy="18" r="3"/>',
        '<circle cx="18" cy="16" r="3"/>',
    ),
    "image": (
        '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>',
        '<circle cx="9" cy="9" r="2"/>',
        '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    ),
    "video": (
        '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/>',
        '<rect x="2" y="6" width="14" height="12" rx="2"/>',
    ),
    "clapperboard": (
        '<path d="M20.2 6 3 11l-.9-2.4c-.3-1.1.3-2.2 1.3-2.5l13.5-4c1.1-.3 2.2.3 2.5 1.3Z"/>',
        '<path d="m6.2 5.3 3.1 3.9"/>',
        '<path d="m12.4 3.4 3.1 4"/>',
        '<path d="M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    ),
    "settings": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>',
        '<circle cx="12" cy="12" r="3"/>',
    ),
    "scroll-text": (
        '<path d="M15 12h-5"/>',
        '<path d="M15 8h-5"/>',
        '<path d="M19 17V5a2 2 0 0 0-2-2H4"/>',
        '<path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
    ),
    "log-out": (
        '<path d="m16 17 5-5-5-5"/>',
        '<path d="M21 12H9"/>',
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>',
    ),
    "store": (
        '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/>',
        '<path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>',
        '<path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/>',
        '<path d="M2 7h20"/>',
        '<path d="M22 7v3a2 2 0 0 1-2 2a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 16 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 12 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 8 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 4 12a2 2 0 0 1-2-2V7"/>',
    ),
    "bell": (
        '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>',
        '<path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    ),
    "youtube": (
        '<path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/>',
        '<path d="m10 15 5-3-5-3z"/>',
    ),
    "x": (
        '<path d="M18 6 6 18"/>',
        '<path d="m6 6 12 12"/>',
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>',
        '<polyline points="7 10 12 15 17 10"/>',
        '<line x1="12" x2="12" y1="15" y2="3"/>',
    ),
}

SIDEBAR_ICON_BY_ROUTE: dict[ShellRouteKey, str] = {
    "home": "gauge",
    "profile": "user-round",
    "workflow": "workflow",
    "progress": "activity",
    "music": "music-4",
    "image": "image",
    "video": "video",
    "studio": "clapperboard",
    "marketplace": "store",
    "merger": "video",
    "settings": "settings",
    "log": "scroll-text",
}

NAV_ICON_COLOR = "#94a3b8"
NAV_ICON_ACTIVE_COLOR = "#e9d5ff"
LOGOUT_ICON_COLOR = "#fda4af"
LOGOUT_ICON_HOVER_COLOR = "#fecdd3"


def lucide_pixmap(name: str, *, size: int, color: str) -> QPixmap:
    paths = _LUCIDE_PATHS.get(name)
    if paths is None:
        raise KeyError(f"Unknown lucide icon: {name}")

    path_tags = "\n  ".join(paths)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">\n  {path_tags}\n</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
