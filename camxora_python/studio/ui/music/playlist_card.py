"""Playlist template preview cards — painted mini-layout thumbnails."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel

from studio.ui.music.playlist_presets import PlaylistPreset


def _qc(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


class PlaylistTemplateCard(QFrame):
    """Selectable card with a hand-painted playlist layout preview."""

    clicked = Signal(str)

    _CARD_W = 168
    _CARD_H = 118
    _PREVIEW_H = 82

    def __init__(self, preset: PlaylistPreset, *, selected: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.preset = preset
        self._selected = selected
        self.setObjectName("PlaylistTemplateCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._CARD_W, self._CARD_H)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(4)

        self._preview = QFrame(self)
        self._preview.setFixedHeight(self._PREVIEW_H)
        self._preview.setObjectName("PlaylistTemplatePreview")
        layout.addWidget(self._preview)

        self._name = QLabel(preset.name)
        self._name.setObjectName("PlaylistTemplateName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._name.setWordWrap(True)
        layout.addWidget(self._name)

        self._apply_frame_style()

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._apply_frame_style()
            self.update()

    def _apply_frame_style(self) -> None:
        from studio.app.theme import PALETTE

        if self._selected:
            self.setStyleSheet(
                f"QFrame#PlaylistTemplateCard {{ background: {PALETTE.panel2};"
                f" border: 2px solid {PALETTE.accent}; border-radius: 10px; }}"
                f"QLabel#PlaylistTemplateName {{ color: #ffffff; font-size: 10px;"
                f" font-weight: 600; background: transparent; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#PlaylistTemplateCard {{ background: {PALETTE.panel2};"
                f" border: 1px solid {PALETTE.border}; border-radius: 10px; }}"
                f"QFrame#PlaylistTemplateCard:hover {{ border-color: {PALETTE.accent}; }}"
                f"QLabel#PlaylistTemplateName {{ color: {PALETTE.text_dim}; font-size: 10px;"
                f" background: transparent; }}"
            )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.preset.id)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        preview_rect = self._preview.geometry()
        painter.setClipRect(preview_rect)
        _paint_playlist_preview(painter, preview_rect, self.preset)
        painter.end()


def _paint_playlist_preview(painter: QPainter, rect, preset: PlaylistPreset) -> None:
    p = preset
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, _qc(p.bg_from))
    grad.setColorAt(1, _qc(p.bg_to))
    path = QPainterPath()
    path.addRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
    painter.fillPath(path, QBrush(grad))

    inner = rect.adjusted(6, 6, -6, -6)
    layout = p.layout
    if layout == "glass_dual":
        _paint_glass_dual(painter, inner, p)
    elif layout == "neon_cyber":
        _paint_neon_cyber(painter, inner, p)
    elif layout == "cover_right":
        _paint_cover_side(painter, inner, p, right=True)
    elif layout == "cover_left":
        _paint_cover_side(painter, inner, p, right=False)
    elif layout == "vol_stack":
        _paint_vol_stack(painter, inner, p)
    elif layout == "neon_circle":
        _paint_neon_circle(painter, inner, p)
    elif layout == "vinyl_peek":
        _paint_vinyl(painter, inner, p)
    elif layout == "wave_bars":
        _paint_wave_bars(painter, inner, p)
    elif layout == "editorial":
        _paint_editorial(painter, inner, p)
    elif layout == "gradient_hero":
        _paint_gradient_hero(painter, inner, p)
    else:
        _paint_minimal_list(painter, inner, p)


def _paint_glass_dual(painter: QPainter, rect, p: PlaylistPreset) -> None:
    mid = rect.center().x()
    left = rect.adjusted(0, 0, -(rect.width() // 2 + 2), 0)
    right = rect.adjusted(rect.width() // 2 + 2, 0, 0, 0)
    painter.fillRect(left, _qc(p.surface, 90))
    painter.fillRect(right, _qc(p.surface, 70))
    painter.setPen(QPen(_qc(p.accent, 180), 1))
    painter.drawLine(mid, rect.top(), mid, rect.bottom())
    for i, y in enumerate(range(int(left.top()) + 8, int(left.bottom()) - 4, 9)):
        w = 28 if i != 1 else 36
        painter.fillRect(left.left() + 4, y, w, 4, _qc(p.muted, 120 if i else 200))
    painter.setBrush(_qc(p.accent, 200))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(right.center().x() - 10, right.center().y() - 10, 20, 20)
    for i, h in enumerate((6, 10, 8, 12, 7)):
        x = right.left() + 8 + i * 5
        painter.fillRect(x, right.bottom() - 14, 3, h, _qc(p.accent2, 180))


def _paint_neon_cyber(painter: QPainter, rect, p: PlaylistPreset) -> None:
    painter.setPen(QPen(_qc(p.accent), 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
    painter.setPen(QPen(_qc(p.accent2), 1))
    for i in range(4):
        y = rect.top() + 10 + i * 11
        painter.fillRect(rect.left() + 6, y, 40 - i * 4, 3, _qc(p.muted, 160))
        painter.drawEllipse(rect.right() - 16, y - 1, 6, 6)


def _paint_cover_side(painter: QPainter, rect, p: PlaylistPreset, *, right: bool) -> None:
    cover_w = int(rect.width() * 0.38)
    if right:
        cover = rect.adjusted(rect.width() - cover_w, 0, 0, 0)
        list_rect = rect.adjusted(0, 0, -cover_w - 3, 0)
    else:
        cover = rect.adjusted(0, 0, -(rect.width() - cover_w), 0)
        list_rect = rect.adjusted(cover_w + 3, 0, 0, 0)
    cover_grad = QLinearGradient(cover.topLeft(), cover.bottomRight())
    cover_grad.setColorAt(0, _qc(p.accent))
    cover_grad.setColorAt(1, _qc(p.accent2))
    painter.fillRect(cover, cover_grad)
    for i in range(4):
        y = list_rect.top() + 6 + i * 10
        painter.fillRect(list_rect.left() + 2, y, list_rect.width() - 8, 3, _qc(p.muted, 140))


def _paint_vol_stack(painter: QPainter, rect, p: PlaylistPreset) -> None:
    thumb = rect.adjusted(0, 0, rect.width() - 40, -(rect.height() - 28))
    painter.fillRect(thumb, _qc(p.accent, 200))
    list_top = thumb.bottom() + 4
    for i in range(3):
        painter.fillRect(rect.left() + 2, list_top + i * 8, rect.width() - 10, 3, _qc(p.muted, 130))


def _paint_neon_circle(painter: QPainter, rect, p: PlaylistPreset) -> None:
    cx = rect.left() + rect.width() // 3
    cy = rect.center().y()
    painter.setPen(QPen(_qc(p.accent), 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(cx - 14, cy - 14, 28, 28)
    painter.setPen(Qt.PenStyle.NoPen)
    for i in range(5):
        h = 4 + (i % 3) * 3
        painter.fillRect(rect.right() - 36 + i * 5, rect.bottom() - 12 - h, 3, h, _qc(p.accent2))


def _paint_vinyl(painter: QPainter, rect, p: PlaylistPreset) -> None:
    cx = rect.left() + 24
    cy = rect.center().y()
    painter.setBrush(_qc("#111111"))
    painter.setPen(QPen(_qc(p.muted), 1))
    painter.drawEllipse(cx - 18, cy - 18, 36, 36)
    painter.setBrush(_qc(p.accent, 120))
    painter.drawEllipse(cx - 6, cy - 6, 12, 12)
    for i in range(4):
        painter.fillRect(cx + 22, rect.top() + 8 + i * 9, 36 - i * 5, 3, _qc(p.muted, 150))


def _paint_wave_bars(painter: QPainter, rect, p: PlaylistPreset) -> None:
    for i in range(8):
        h = 6 + ((i * 5) % 13)
        x = rect.left() + 6 + i * 8
        painter.fillRect(x, rect.bottom() - 8 - h, 5, h, _qc(p.accent if i % 2 else p.accent2, 200))
    for i in range(3):
        painter.fillRect(rect.left() + 4, rect.top() + 6 + i * 8, rect.width() - 12, 2, _qc(p.muted, 100))


def _paint_editorial(painter: QPainter, rect, p: PlaylistPreset) -> None:
    font = QFont("Georgia", 7)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(_qc(p.accent))
    painter.drawText(rect.adjusted(4, 2, -4, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, "PLAYLIST")
    for i in range(4):
        y = rect.top() + 18 + i * 9
        painter.fillRect(rect.left() + 8, y, rect.width() - 16, 2, _qc(p.muted, 120))


def _paint_gradient_hero(painter: QPainter, rect, p: PlaylistPreset) -> None:
    overlay = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    overlay.setColorAt(0, _qc(p.accent, 40))
    overlay.setColorAt(1, _qc(p.bg_to, 200))
    painter.fillRect(rect, overlay)
    font = QFont("Open Sans", 6)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(_qc(p.muted))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "NOW\nPLAYING")


def _paint_minimal_list(painter: QPainter, rect, p: PlaylistPreset) -> None:
    for i in range(5):
        y = rect.top() + 5 + i * 10
        alpha = 200 - i * 25
        w = rect.width() - 12 - (i * 3)
        painter.fillRect(rect.left() + 4, y, w, 3, _qc(p.muted, alpha))
