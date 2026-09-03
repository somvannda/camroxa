"""Semi-transparent drop preview shown while dragging from the library."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from studio.ui.timeline.geometry import CLIP_HEIGHT, MIN_CLIP_WIDTH_PX, TRACK_HEIGHT

_TYPE_COLORS = {
    "video": ("#8a6bff", "#6a4de0"),
    "audio": ("#2fe6b4", "#18a880"),
    "image": ("#ffc36b", "#e69a2e"),
    "text": ("#ffc36b", "#e69a2e"),
    "overlay": ("#ffc36b", "#e69a2e"),
}


class DropGhostItem(QGraphicsObject):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._label = ""
        self._media_type = "video"
        self._width_px = MIN_CLIP_WIDTH_PX
        self._row_index = 0
        self._magnetized = False
        self.setZValue(15)
        self.setOpacity(0.72)
        self.hide()

    def show_at(
        self,
        row_index: int,
        start_px: float,
        width_px: float,
        label: str,
        media_type: str,
        *,
        magnetized: bool = False,
    ) -> None:
        self._row_index = max(0, row_index)
        self._width_px = max(MIN_CLIP_WIDTH_PX, width_px)
        self._label = label
        self._media_type = media_type
        self._magnetized = magnetized
        y = self._row_index * TRACK_HEIGHT + (TRACK_HEIGHT - CLIP_HEIGHT) / 2
        self.setPos(start_px, y)
        self.show()
        self.update()

    def hide_ghost(self) -> None:
        self.hide()

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(0, 0, self._width_px, CLIP_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:  # noqa: N802
        rect = self.boundingRect()
        color_from, _color_to = _TYPE_COLORS.get(self._media_type, _TYPE_COLORS["video"])
        if self._magnetized:
            painter.setPen(QPen(QColor("#ffd54a"), 3, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(QColor(color_from)))
            painter.setOpacity(0.95)
        else:
            painter.setPen(QPen(QColor("#ffd54a"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(color_from)))
        painter.drawRoundedRect(rect, 6, 6)
        if self._magnetized:
            painter.setPen(QColor("#ffd54a"))
            font = painter.font()
            font.setPixelSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect.adjusted(4, 2, -4, -2), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, "SNAP")
        painter.setPen(QColor("#0a0a0f"))
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(6, 2, -4, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._label)
