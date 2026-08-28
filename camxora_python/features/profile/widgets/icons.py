"""Small painted icons used only by the Profile workspace."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

from features.create.create_styles import STUDIO_AVATAR_COLORS, STUDIO_PURPLE, STUDIO_PURPLE_BRIGHT, STUDIO_TEXT_DIM
from shared.icons.lucide_icons import lucide_pixmap

_EXTRA_PATHS: dict[str, tuple[str, ...]] = {
    "plus": (
        '<path d="M5 12h14"/>',
        '<path d="M12 5v14"/>',
    ),
    "funnel": (
        '<path d="M3 5h18l-7 8v5l-4 2v-7z"/>',
    ),
    "ellipsis-vertical": (
        '<circle cx="12" cy="5" r="1"/>',
        '<circle cx="12" cy="12" r="1"/>',
        '<circle cx="12" cy="19" r="1"/>',
    ),
    "coins": (
        '<circle cx="9" cy="9" r="7"/>',
        '<path d="M9 6v6"/>',
        '<path d="M7.5 9h3"/>',
        '<path d="M16 10.5a7 7 0 0 1-3 11.4"/>',
    ),
    "hash": (
        '<line x1="4" x2="20" y1="9" y2="9"/>',
        '<line x1="4" x2="20" y1="15" y2="15"/>',
        '<line x1="10" x2="8" y1="3" y2="21"/>',
        '<line x1="16" x2="14" y1="3" y2="21"/>',
    ),
    "hard-drive": (
        '<line x1="22" x2="2" y1="12" y2="12"/>',
        '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
        '<line x1="6" x2="6.01" y1="16" y2="16"/>',
        '<line x1="10" x2="10.01" y1="16" y2="16"/>',
    ),
}


def field_icon(name: str, *, size: int = 14, color: str = STUDIO_TEXT_DIM) -> QIcon:
    return QIcon(profile_icon(name, size=size, color=color))


def profile_icon(name: str, *, size: int, color: str) -> QPixmap:
    if name in _EXTRA_PATHS:
        path_tags = "\n  ".join(_EXTRA_PATHS[name])
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
    return lucide_pixmap(name, size=size, color=color)


def initials_from_name(name: str) -> str:
    parts = [part for part in str(name or "").split() if part]
    if not parts:
        return "—"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def color_for_name(name: str) -> str:
    if not name:
        return STUDIO_AVATAR_COLORS[0]
    return STUDIO_AVATAR_COLORS[sum(ord(ch) for ch in name) % len(STUDIO_AVATAR_COLORS)]


def paint_initials_avatar(
    size: int,
    initials: str,
    *,
    color: str | None = None,
) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(QPointF(0, 0), QPointF(size, size))
    gradient.setColorAt(0.0, QColor(color or STUDIO_PURPLE))
    gradient.setColorAt(1.0, QColor(STUDIO_PURPLE_BRIGHT if color is None else color))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QRectF(0, 0, size, size))
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setFamily("Inter")
    font.setPixelSize(max(11, int(size * 0.36)))
    font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, initials[:2])
    painter.end()
    return pixmap


def indicator_pixmap(color: str, size: int = 10) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    inset = 1
    painter.drawRoundedRect(QRectF(inset, inset, size - inset * 2, size - inset * 2), 2, 2)
    painter.end()
    return pixmap


def icon_tile(
    name: str,
    *,
    color: str,
    tile: int = 28,
    icon: int = 14,
) -> QPixmap:
    pixmap = QPixmap(tile, tile)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    glow = QColor(color)
    glow.setAlpha(38)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawRoundedRect(QRectF(0, 0, tile, tile), 6, 6)
    painter.setBrush(QColor("#101F32"))
    painter.setPen(QPen(QColor(color), 1))
    inset = 0.5
    painter.drawRoundedRect(QRectF(inset, inset, tile - 1, tile - 1), 6, 6)
    glyph = profile_icon(name, size=icon, color=color)
    origin = (tile - icon) // 2
    painter.drawPixmap(origin, origin, glyph)
    painter.end()
    return pixmap


def visibility_dot(color: str, size: int = 8) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(QRectF(0, 0, size, size))
    painter.end()
    return pixmap

