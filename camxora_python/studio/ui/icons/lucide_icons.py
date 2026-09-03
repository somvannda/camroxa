"""Lucide stroke icons rendered as tinted SVG pixmaps for Qt widgets.

Uses the same paths as the Lucide icon set (lucide-static, ISC license).
Qt renders them as crisp vector strokes — visually identical to Lucide font
icons but without bundling a separate icon font file.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt, QPointF
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QPolygonF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton, QToolButton

from studio.app.theme import PALETTE
from studio.ui.icons.lucide_paths import LUCIDE_PLAY_POLYGON, play_icon_scale_for_diameter

# Standard icon/button sizes — keep toolbar + transport visually consistent.
ICON_SZ_TOOLBAR = 14
ICON_SZ_INSPECTOR_ALIGN = 14
ICON_SZ_MASK_SHAPE = 24
ICON_SZ_ANIMATION = 18
ICON_SZ_TRANSPORT = 14
ICON_SZ_PLAY = 14
ICON_SZ_HEADER = 12
ICON_SZ_LIBRARY = 22
ICON_SZ_CLIP_STRIP = 10

BTN_SZ_TOOLBAR = 28
BTN_SZ_ICON = 32
BTN_SZ_PLAY = 34

# Paths from lucide-static (ISC) — viewBox 0 0 24 24
_LUCIDE_PATHS: dict[str, tuple[str, ...]] = {
    "play": (
        f'<polygon points="{" ".join(f"{x:g} {y:g}" for x, y in LUCIDE_PLAY_POLYGON)}"/>',
    ),
    "pause": (
        '<rect x="14" y="4" width="4" height="16" rx="1"/>',
        '<rect x="6" y="4" width="4" height="16" rx="1"/>',
    ),
    "skip-back": (
        '<polygon points="19 20 9 12 19 4 19 20"/>',
        '<line x1="5" x2="5" y1="19" y2="5"/>',
    ),
    "skip-forward": (
        '<polygon points="5 4 15 12 5 20 5 4"/>',
        '<line x1="19" x2="19" y1="5" y2="19"/>',
    ),
    "scissors": (
        '<circle cx="6" cy="6" r="3"/>',
        '<circle cx="6" cy="18" r="3"/>',
        '<line x1="20" x2="8.12" y1="4" y2="15.88"/>',
        '<line x1="14.47" x2="20" y1="14.48" y2="20"/>',
        '<line x1="8.12" x2="12" y1="8.12" y2="12"/>',
    ),
    "trash-2": (
        '<path d="M3 6h18"/>',
        '<path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>',
        '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
        '<line x1="10" x2="10" y1="11" y2="17"/>',
        '<line x1="14" x2="14" y1="11" y2="17"/>',
    ),
    "magnet": (
        '<path d="m6 15-4-4V6a2 2 0 0 1 2-2h3"/>',
        '<path d="m18 15 4-4V6a2 2 0 0 0-2-2h-3"/>',
        '<path d="M6 11V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v7"/>',
        '<path d="M6 15h12"/>',
    ),
    "settings": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>',
        '<circle cx="12" cy="12" r="3"/>',
    ),
    "undo-2": (
        '<path d="M9 14 4 9l5-5"/>',
        '<path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11"/>',
    ),
    "redo-2": (
        '<path d="m15 14 5-5-5-5"/>',
        '<path d="M20 9H9.5A5.5 5.5 0 0 0 4 14.5a5.5 5.5 0 0 0 5.5 5.5H13"/>',
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>',
        '<polyline points="7 10 12 15 17 10"/>',
        '<line x1="12" x2="12" y1="15" y2="3"/>',
    ),
    "upload": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>',
        '<polyline points="17 8 12 3 7 8"/>',
        '<line x1="12" x2="12" y1="3" y2="15"/>',
    ),
    "plus": (
        '<path d="M5 12h14"/>',
        '<path d="M12 5v14"/>',
    ),
    "video": (
        '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/>',
        '<rect x="2" y="6" width="14" height="12" rx="2"/>',
    ),
    "music-2": (
        '<circle cx="8" cy="18" r="4"/>',
        '<path d="M12 18V2l7 4"/>',
    ),
    "image": (
        '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>',
        '<circle cx="9" cy="9" r="2"/>',
        '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    ),
    "type": (
        '<polyline points="4 7 4 4 20 4 20 16 16 16"/>',
        '<line x1="9" x2="20" y1="20" y2="9"/>',
    ),
    "layers": (
        '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/>',
        '<path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/>',
        '<path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    ),
    "grip-vertical": (
        '<circle cx="9" cy="12" r="1"/>',
        '<circle cx="9" cy="5" r="1"/>',
        '<circle cx="9" cy="19" r="1"/>',
        '<circle cx="15" cy="12" r="1"/>',
        '<circle cx="15" cy="5" r="1"/>',
        '<circle cx="15" cy="19" r="1"/>',
    ),
    "volume-2": (
        '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>',
        '<path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>',
    ),
    "volume-x": (
        '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>',
        '<line x1="22" x2="16" y1="9" y2="15"/>',
        '<line x1="16" x2="22" y1="9" y2="15"/>',
    ),
    "headphones": (
        '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>',
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>',
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    ),
    "lock-open": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>',
        '<path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
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
    "loader-2": (
        '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    ),
    "file": (
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>',
        '<path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    ),
    "arrow-left-right": (
        '<path d="m16 3 4 4-4 4"/>',
        '<path d="M20 7H4"/>',
        '<path d="m8 21-4-4 4-4"/>',
        '<path d="M4 17h16"/>',
    ),
    "link-2": (
        '<path d="M9 17H7A5 5 0 0 1 7 7h2"/>',
        '<path d="M15 7h2a5 5 0 1 1 0 10h-2"/>',
        '<line x1="8" x2="16" y1="12" y2="12"/>',
    ),
    "mic": (
        '<path d="M12 19v3"/>',
        '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>',
        '<rect x="9" y="2" width="6" height="13" rx="3"/>',
    ),
    "maximize": (
        '<path d="M8 3H5a2 2 0 0 0-2 2v3"/>',
        '<path d="M21 8V5a2 2 0 0 0-2-2h-3"/>',
        '<path d="M3 16v3a2 2 0 0 0 2 2h3"/>',
        '<path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    ),
    "ratio": (
        '<rect width="12" height="20" x="6" y="2" rx="2"/>',
        '<rect width="20" height="12" x="2" y="6" rx="2"/>',
    ),
    "sparkles": (
        '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
        '<path d="M20 3v4"/>',
        '<path d="M22 5h-4"/>',
        '<path d="M4 17v2"/>',
        '<path d="M5 18H3"/>',
    ),
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>',
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    ),
    "unlink": (
        '<path d="m18.84 12.25 1.72-1.71h-.02a5.004 5.004 0 0 0-.12-7.07 5.006 5.006 0 0 0-6.95 0l-1.72 1.71"/>',
        '<path d="m5.17 11.75-1.71 1.71a5.004 5.004 0 0 0 .12 7.07 5.006 5.006 0 0 0 6.95 0l1.71-1.71"/>',
        '<line x1="8" x2="8" y1="2" y2="5"/>',
        '<line x1="2" x2="5" y1="8" y2="8"/>',
        '<line x1="16" x2="16" y1="19" y2="22"/>',
        '<line x1="19" x2="22" y1="16" y2="16"/>',
    ),
    # Inspector alignment toolbar (CapCut-style bar + lines)
    "align-left": (
        '<line x1="4" x2="4" y1="5" y2="19"/>',
        '<line x1="8" x2="20" y1="8" y2="8"/>',
        '<line x1="8" x2="18" y1="12" y2="12"/>',
        '<line x1="8" x2="20" y1="16" y2="16"/>',
    ),
    "align-h-center": (
        '<line x1="12" x2="12" y1="5" y2="19"/>',
        '<line x1="8" x2="16" y1="8" y2="8"/>',
        '<line x1="6" x2="18" y1="12" y2="12"/>',
        '<line x1="8" x2="16" y1="16" y2="16"/>',
    ),
    "align-right": (
        '<line x1="20" x2="20" y1="5" y2="19"/>',
        '<line x1="4" x2="16" y1="8" y2="8"/>',
        '<line x1="6" x2="18" y1="12" y2="12"/>',
        '<line x1="4" x2="16" y1="16" y2="16"/>',
    ),
    "align-top": (
        '<line x1="5" x2="19" y1="4" y2="4"/>',
        '<line x1="8" x2="8" y1="8" y2="20"/>',
        '<line x1="12" x2="12" y1="8" y2="18"/>',
        '<line x1="16" x2="16" y1="8" y2="20"/>',
    ),
    "align-v-center": (
        '<line x1="5" x2="19" y1="12" y2="12"/>',
        '<line x1="8" x2="8" y1="6" y2="18"/>',
        '<line x1="12" x2="12" y1="8" y2="20"/>',
        '<line x1="16" x2="16" y1="6" y2="18"/>',
    ),
    "align-bottom": (
        '<line x1="5" x2="19" y1="20" y2="20"/>',
        '<line x1="8" x2="8" y1="4" y2="16"/>',
        '<line x1="12" x2="12" y1="6" y2="18"/>',
        '<line x1="16" x2="16" y1="4" y2="16"/>',
    ),
    "distribute-h": (
        '<line x1="6" x2="6" y1="6" y2="18"/>',
        '<line x1="12" x2="12" y1="8" y2="16"/>',
        '<line x1="18" x2="18" y1="6" y2="18"/>',
    ),
    "distribute-v": (
        '<line x1="6" x2="18" y1="6" y2="6"/>',
        '<line x1="8" x2="16" y1="12" y2="12"/>',
        '<line x1="6" x2="18" y1="18" y2="18"/>',
    ),
    # Animation preset icons
    "circle-slash": (
        '<circle cx="12" cy="12" r="10"/>',
        '<line x1="4.93" x2="19.07" y1="4.93" y2="19.07"/>',
    ),
    "zoom-in": (
        '<circle cx="11" cy="11" r="8"/>',
        '<line x1="21" x2="16.65" y1="21" y2="16.65"/>',
        '<line x1="11" x2="11" y1="8" y2="14"/>',
        '<line x1="8" x2="14" y1="11" y2="11"/>',
    ),
    "zoom-out": (
        '<circle cx="11" cy="11" r="8"/>',
        '<line x1="21" x2="16.65" y1="21" y2="16.65"/>',
        '<line x1="8" x2="14" y1="11" y2="11"/>',
    ),
    "sunrise": (
        '<path d="M12 2v8"/>',
        '<path d="m4.93 10.93 1.41 1.41"/>',
        '<path d="M2 18h2"/>',
        '<path d="M20 18h2"/>',
        '<path d="m19.07 10.93-1.41 1.41"/>',
        '<path d="M22 22H2"/>',
        '<path d="m16 18-4-4-4 4"/>',
    ),
    "sunset": (
        '<path d="M12 10V2"/>',
        '<path d="m4.93 10.93 1.41 1.41"/>',
        '<path d="M2 18h2"/>',
        '<path d="M20 18h2"/>',
        '<path d="m19.07 10.93-1.41 1.41"/>',
        '<path d="M22 22H2"/>',
        '<path d="m8 14 4 4 4-4"/>',
    ),
    "move-right": (
        '<path d="M18 8 22 12 18 16"/>',
        '<path d="M2 12h20"/>',
    ),
    "move-left": (
        '<path d="m6 8-4 4 4 4"/>',
        '<path d="M2 12h20"/>',
    ),
    "maximize-2": (
        '<polyline points="15 3 21 3 21 9"/>',
        '<polyline points="9 21 3 21 3 15"/>',
        '<line x1="21" x2="14" y1="3" y2="10"/>',
        '<line x1="3" x2="10" y1="21" y2="14"/>',
    ),
    "activity": (
        '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    ),
    "vibrate": (
        '<path d="m2 8 2 2-2 2 2 2-2 2"/>',
        '<path d="m18 8 2 2-2 2 2 2-2 2"/>',
        '<rect width="8" height="14" x="8" y="5" rx="1"/>',
    ),
    "arrow-up-down": (
        '<path d="m21 16-4 4-4-4"/>',
        '<path d="M17 20V4"/>',
        '<path d="m3 8 4-4 4 4"/>',
        '<path d="M7 4v16"/>',
    ),
    "rotate-cw": (
        '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/>',
        '<path d="M21 3v5h-5"/>',
    ),
    "audio-lines": (
        '<path d="M2 10v3"/>',
        '<path d="M6 6v11"/>',
        '<path d="M10 3v18"/>',
        '<path d="M14 8v7"/>',
        '<path d="M18 5v13"/>',
        '<path d="M22 10v3"/>',
    ),
    # Mask shape icons
    "mask-split": (
        '<rect x="4" y="4" width="16" height="16" rx="2"/>',
        '<path d="M4 20 20 4"/>',
    ),
    "mask-filmstrip": (
        '<rect x="4" y="5" width="16" height="14" rx="2"/>',
        '<line x1="4" x2="20" y1="9" y2="9"/>',
        '<line x1="4" x2="20" y1="13" y2="13"/>',
        '<line x1="4" x2="20" y1="17" y2="17"/>',
    ),
    "mask-circle": ('<circle cx="12" cy="12" r="9"/>',),
    "mask-rectangle": ('<rect x="5" y="5" width="14" height="14" rx="2"/>',),
    "mask-star": (
        '<path d="m12 3 2.09 6.26L20 9.27l-5 3.64L16.18 20 12 16.77 7.82 20 9 12.91l-5-3.64 5.91-.91z"/>',
    ),
    "mask-heart": (
        '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    ),
    "mask-brush": (
        '<path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/>',
        '<path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z"/>',
    ),
    "mask-pen": (
        '<path d="M12 20h9"/>',
        '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    ),
}

TRACK_TYPE_ICON = {"video": "video", "audio": "music-2", "overlay": "layers"}
MEDIA_TYPE_ICON = {"video": "video", "audio": "music-2", "image": "image"}
CLIP_KIND_ICON = {"video": "video", "audio": "music-2", "image": "image", "text": "type", "playlist": "layout-grid"}
SCENE_ROLE_ICON = {
    "playlist_background": "image",
    "playlist_graphics": "layout-grid",
    "playlist_audio": "music-2",
}
SCENE_ROLE_ACCENT = {
    "playlist_background": "#64748b",
    "playlist_graphics": "#7466F1",
    "playlist_audio": "#2fe6b4",
}

ICON_COLOR = PALETTE.text
ICON_COLOR_DIM = PALETTE.text_dim
ICON_COLOR_ON_ACCENT = "#ffffff"
ICON_COLOR_ACTIVE = "#ffd54a"


def _stroke_width(size: int) -> float:
    if size <= 12:
        return 1.65
    if size <= 16:
        return 1.75
    return 2.0


def lucide_pixmap(name: str, *, size: int, color: str) -> QPixmap:
    paths = _LUCIDE_PATHS.get(name)
    if paths is None:
        paths = _LUCIDE_PATHS["sparkles"]

    stroke = _stroke_width(size)
    path_tags = "\n  ".join(paths)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">\n  {path_tags}\n</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    return pixmap


def lucide_icon(name: str, *, size: int, color: str) -> QIcon:
    return QIcon(lucide_pixmap(name, size=size, color=color))


def lucide_play_filled_pixmap(
    *,
    size: int,
    color: str,
    bg: str | None = None,
) -> QPixmap:
    """Filled Lucide play on an optional circular background (playlist rows)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if bg:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawEllipse(0, 0, size, size)
    points = []
    scale = play_icon_scale_for_diameter(size)
    ox, oy = 13.0, 12.0
    nudge = 0.85 * scale
    cx = size / 2.0
    cy = size / 2.0
    for x, y in LUCIDE_PLAY_POLYGON:
        points.append(QPointF(cx + (x - ox) * scale + nudge, cy + (y - oy) * scale))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    return pix


def set_button_lucide_icon(
    button: QPushButton | QToolButton,
    name: str,
    *,
    size: int = ICON_SZ_TOOLBAR,
    color: str = ICON_COLOR,
    clear_text: bool = True,
) -> None:
    if clear_text:
        button.setText("")
    button.setIcon(lucide_icon(name, size=size, color=color))
    button.setIconSize(QSize(size, size))


def track_badge_pixmap(
    track_type: str,
    *,
    size: int = 22,
    icon_px: int = 12,
    scene_role: str | None = None,
) -> QPixmap:
    from studio.ui.timeline.geometry import TRACK_ACCENT

    if scene_role and scene_role in SCENE_ROLE_ACCENT:
        bg = SCENE_ROLE_ACCENT[scene_role]
        icon_name = SCENE_ROLE_ICON.get(scene_role, "layers")
    else:
        bg = TRACK_ACCENT.get(track_type, "#7c5cff")
        icon_name = TRACK_TYPE_ICON.get(track_type, "layers")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(bg))
    painter.drawRoundedRect(0, 0, size, size, 5, 5)
    icon = lucide_pixmap(icon_name, size=icon_px, color="#0a0a0f")
    offset = (size - icon_px) // 2
    painter.drawPixmap(offset, offset, icon)
    painter.end()
    return pix
