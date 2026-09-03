"""Mini preview cards for track-list sub-templates."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from studio.core.playlist_assets import bundled_thumbnail_path
from studio.core.playlist_sub_templates import PlaylistSubTemplate
from studio.ui.icons.lucide_icons import lucide_play_filled_pixmap
from studio.ui.icons.lucide_paths import PLAY_PREVIEW_DIAMETER, play_diameter_for_row


def _qc(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


class PlaylistSubTemplateCard(QFrame):
    clicked = Signal(str)

    _W = 132
    _H = 112
    _PREVIEW_H = 78

    def __init__(self, sub: PlaylistSubTemplate, *, selected: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.sub = sub
        self._selected = selected
        self.setObjectName("PlaylistSubTemplateCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._W, self._H)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(4)

        self._preview = QFrame()
        self._preview.setFixedHeight(self._PREVIEW_H)
        self._preview.setObjectName("PlaylistSubTemplatePreview")
        layout.addWidget(self._preview)

        self._name = QLabel(sub.name)
        self._name.setObjectName("PlaylistTemplateName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._name.setWordWrap(True)
        layout.addWidget(self._name)
        self._thumbnail_pixmap: QPixmap | None = None
        thumb_path = bundled_thumbnail_path(sub.id)
        if thumb_path is not None:
            loaded = QPixmap(str(thumb_path))
            if not loaded.isNull():
                self._thumbnail_pixmap = loaded
        self._apply_frame_style()

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._apply_frame_style()
            self.update()

    def _apply_frame_style(self) -> None:
        from app.theme import PALETTE

        p = PALETTE
        if self._selected:
            self.setStyleSheet(
                f"QFrame#PlaylistSubTemplateCard {{ background: {p.panel2};"
                f" border: 2px solid {p.accent}; border-radius: 10px; }}"
                f"QLabel#PlaylistTemplateName {{ color: #ffffff; font-size: 10px; font-weight: 600; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#PlaylistSubTemplateCard {{ background: {p.panel2};"
                f" border: 1px solid {p.border}; border-radius: 10px; }}"
                f"QFrame#PlaylistSubTemplateCard:hover {{ border-color: {p.accent}; }}"
                f"QLabel#PlaylistTemplateName {{ color: {p.text_dim}; font-size: 10px; }}"
            )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.sub.id)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        rect = self._preview.geometry()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._thumbnail_pixmap is not None:
            _paint_thumbnail_preview(painter, rect, self._thumbnail_pixmap)
            painter.end()
            return
        painter.setClipRect(rect)
        _paint_track_list_preview(painter, rect, self.sub)
        painter.end()


def _paint_thumbnail_preview(painter: QPainter, rect, pixmap: QPixmap) -> None:
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setClipRect(rect)
    scaled = pixmap.scaled(
        rect.size(),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = rect.x() + (rect.width() - scaled.width()) // 2
    y = rect.y() + (rect.height() - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)


def _paint_track_list_preview(painter: QPainter, rect, sub: PlaylistSubTemplate) -> None:
    if sub.layout_style == "minimal_white":
        _paint_minimal_white_preview(painter, rect, sub)
        return

    c = sub.colors
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, _qc(c.get("bg_from", "#111")))
    grad.setColorAt(1, _qc(c.get("bg_to", "#000")))
    painter.fillRect(rect, QBrush(grad))

    card = rect.adjusted(8, 8, -8, -8)
    surface = _qc(c.get("surface", "#ffffff22"))
    if sub.glass:
        surface.setAlpha(90)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(surface)
    painter.drawRoundedRect(card, 6, 6)

    if sub.neon_border:
        painter.setPen(QPen(_qc(c.get("accent", "#f0f")), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(card, 6, 6)

    text = _qc(c.get("text", "#fff"))
    muted = _qc(c.get("muted", "#888"))
    accent = _qc(c.get("accent", "#7466F1"))
    selected = _qc(c.get("selected_row", "#7466F144"))

    font = QFont("Open Sans", 7, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(text)
    painter.drawText(card.adjusted(6, 4, -6, 0), Qt.AlignmentFlag.AlignLeft, "TRACK LIST")

    row_h = 9
    y0 = card.top() + 16
    for i in range(4):
        y = y0 + i * row_h
        row_rect = card.adjusted(4, y - card.top(), -4, y - card.top() + row_h - 1)
        if i == 1:
            painter.setBrush(selected)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(row_rect, 3, 3)
        painter.setPen(accent if i == 1 else muted)
        painter.drawText(row_rect.adjusted(4, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"0{i + 1}")
        painter.setPen(text if i == 1 else muted)
        painter.drawText(row_rect.adjusted(16, 0, -20, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "Song title")
        painter.setPen(muted)
        painter.drawText(row_rect.adjusted(0, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "04:21")


def _paint_minimal_white_preview(painter: QPainter, rect, sub: PlaylistSubTemplate) -> None:
    c = sub.colors
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0, _qc(c.get("bg_from", "#e8eaee")))
    grad.setColorAt(1, _qc(c.get("bg_to", "#f5f6f8")))
    painter.fillRect(rect, QBrush(grad))

    card = rect.adjusted(10, 6, -10, -6)
    shadow = card.adjusted(0, 3, 0, 3)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_qc("#000000", 28))
    painter.drawRoundedRect(shadow, 8, 8)
    painter.setBrush(_qc(c.get("surface", "#ffffff")))
    painter.drawRoundedRect(card, 8, 8)

    text = _qc(c.get("text", "#000000"))
    muted = _qc(c.get("muted", "#8e8e93"))
    selected = _qc(c.get("selected_row", "#f2f2f7"))
    play_icon = _qc(c.get("play_icon", text))

    font = QFont("Open Sans", 7, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(text)
    painter.drawText(card.adjusted(8, 5, -8, 0), Qt.AlignmentFlag.AlignLeft, "TRACK LIST")

    row_h = 14
    y0 = card.top() + 18
    for i in range(3):
        row_rect = card.adjusted(6, y0 - card.top() + i * row_h, -6, y0 - card.top() + (i + 1) * row_h - 2)
        if i == 0:
            painter.setBrush(selected)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(row_rect, 4, 4)
            painter.setBrush(_qc("#ffffff"))
            painter.drawEllipse(row_rect.left() + 16, row_rect.center().y() - 4, 8, 8)
        else:
            btn_size = min(PLAY_PREVIEW_DIAMETER, play_diameter_for_row(row_h))
            cx = row_rect.left() + 19
            cy = row_rect.center().y()
            play_pix = lucide_play_filled_pixmap(
                size=btn_size,
                color=play_icon.name(),
                bg=c.get("button_inactive", "#ececef"),
            )
            painter.drawPixmap(int(cx - btn_size // 2), int(cy - btn_size // 2), play_pix)
        painter.setPen(text)
        painter.setFont(QFont("Open Sans", 6, QFont.Weight.DemiBold if i == 0 else QFont.Weight.Normal))
        painter.drawText(row_rect.adjusted(26, 1, -18, 0), Qt.AlignmentFlag.AlignLeft, "Song title")
        painter.setPen(text)
        painter.drawText(row_rect.adjusted(0, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "04:21")
