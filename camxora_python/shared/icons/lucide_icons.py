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
    # Soft “update available” header affordance (reads clearly on #060b20).
    "arrow-up-circle": (
        '<circle cx="12" cy="12" r="10"/>',
        '<path d="m16 12-4-4-4 4"/>',
        '<path d="M12 16V8"/>',
    ),
    "sparkles": (
        '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
        '<path d="M20 3v4"/>',
        '<path d="M22 5h-4"/>',
        '<path d="M4 17v2"/>',
        '<path d="M5 18H3"/>',
    ),
    "folder-open": (
        '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    ),
    "search": (
        '<circle cx="11" cy="11" r="8"/>',
        '<path d="m21 21-4.3-4.3"/>',
    ),
    "refresh-cw": (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>',
        '<path d="M21 3v5h-5"/>',
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>',
        '<path d="M8 16H3v5"/>',
    ),
    "info": (
        '<circle cx="12" cy="12" r="10"/>',
        '<path d="M12 16v-4"/>',
        '<path d="M12 8h.01"/>',
    ),
    "volume-2": (
        '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/>',
        '<path d="M16 9a5 5 0 0 1 0 6"/>',
        '<path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',
    ),
    "circle-help": (
        '<circle cx="12" cy="12" r="10"/>',
        '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>',
        '<path d="M12 17h.01"/>',
    ),
    "mail": (
        '<path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"/>',
        '<rect x="2" y="4" width="20" height="16" rx="2"/>',
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>',
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    ),
    "eye": (
        '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/>',
        '<circle cx="12" cy="12" r="3"/>',
    ),
    "eye-off": (
        '<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/>',
        '<path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/>',
        '<path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/>',
        '<path d="m2 2 20 20"/>',
    ),
    "log-in": (
        '<path d="m10 17 5-5-5-5"/>',
        '<path d="M15 12H3"/>',
        '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>',
    ),
    "chevron-left": (
        '<path d="m15 18-6-6 6-6"/>',
    ),
    "chevron-right": (
        '<path d="m9 18 6-6-6-6"/>',
    ),
    "chevron-down": (
        '<path d="m6 9 6 6 6-6"/>',
    ),
    "chevron-up": (
        '<path d="m18 15-6-6-6 6"/>',
    ),
    "calendar": (
        '<path d="M8 2v4"/>',
        '<path d="M16 2v4"/>',
        '<rect width="18" height="18" x="3" y="4" rx="2"/>',
        '<path d="M3 10h18"/>',
    ),
    "check": (
        '<path d="M20 6 9 17l-5-5"/>',
    ),
    "triangle-alert": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>',
        '<path d="M12 9v4"/>',
        '<path d="M12 17h.01"/>',
    ),
    "filter": (
        '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    ),
    "list": (
        '<path d="M3 12h.01"/>',
        '<path d="M3 18h.01"/>',
        '<path d="M3 6h.01"/>',
        '<path d="M8 12h13"/>',
        '<path d="M8 18h13"/>',
        '<path d="M8 6h13"/>',
    ),
    "play": (
        '<polygon points="6 3 20 12 6 21 6 3"/>',
    ),
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>',
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    ),
    "layers": (
        '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/>',
        '<path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/>',
        '<path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/>',
    ),
    "clock": (
        '<circle cx="12" cy="12" r="10"/>',
        '<polyline points="12 6 12 12 16 14"/>',
    ),
    "plus": (
        '<path d="M5 12h14"/>',
        '<path d="M12 5v14"/>',
    ),
    "trash-2": (
        '<path d="M3 6h18"/>',
        '<path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>',
        '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
        '<path d="M10 11v6"/>',
        '<path d="M14 11v6"/>',
    ),
}

SIDEBAR_ICON_BY_ROUTE: dict[ShellRouteKey, str] = {
    "home": "gauge",
    "profile": "user-round",
    "workflow": "workflow",
    "progress": "activity",
    "music": "music-4",
    "create": "music-4",
    "studio": "layers",
    "image": "image",
    "video": "video",
    "marketplace": "store",
    "merger": "video",
    "settings": "settings",
    "log": "scroll-text",
}

NAV_ICON_COLOR = "#8FA4BB"
NAV_ICON_ACTIVE_COLOR = "#E5EDF7"
LOGOUT_ICON_COLOR = "#8FA4BB"
LOGOUT_ICON_HOVER_COLOR = "#E5EDF7"


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
