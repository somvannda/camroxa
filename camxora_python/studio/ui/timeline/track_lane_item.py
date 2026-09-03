"""Track lane background — accent stripe, alternating fill, grid, empty-slot hints."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QStyleOptionGraphicsItem, QWidget

from studio.ui.timeline.geometry import (
    EMPTY_LANE_HINT_GENERIC,
    LANE_STRIPE_WIDTH,
    TRACK_ACCENT,
    TRACK_LANE_BG,
    ruler_step_seconds,
    ruler_sub_step_seconds,
)

_EMPTY_STRIPE = "#3a3a48"


class TrackLaneItem(QGraphicsRectItem):
    def __init__(
        self,
        row_index: int,
        track_type: str | None,
        is_empty_slot: bool,
        total_width: float,
        px_per_sec: float,
        duration: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._row_index = row_index
        self._track_type = track_type
        self._is_empty_slot = is_empty_slot
        self._px_per_sec = px_per_sec
        self._duration = duration
        self.setPen(Qt.PenStyle.NoPen)
        self.setZValue(-10)
        self.setRect(QRectF(0, 0, total_width, 0))

    def configure(
        self,
        y: float,
        height: float,
        total_width: float,
        track_type: str | None,
        is_empty_slot: bool,
        px_per_sec: float,
        duration: float,
    ) -> None:
        self._track_type = track_type
        self._is_empty_slot = is_empty_slot
        self._px_per_sec = px_per_sec
        self._duration = duration
        self.setRect(QRectF(0, y, total_width, height))
        self.update()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:  # noqa: N802
        rect = self.rect()
        bg = QColor(TRACK_LANE_BG[self._row_index % 2])
        painter.fillRect(rect, bg)

        if self._is_empty_slot:
            accent_color = QColor(_EMPTY_STRIPE)
        else:
            accent_color = QColor(TRACK_ACCENT.get(self._track_type or "video", "#7c5cff"))

        stripe = QRectF(rect.left(), rect.top(), LANE_STRIPE_WIDTH, rect.height())
        painter.fillRect(stripe, accent_color)

        if self._px_per_sec > 0:
            self._paint_grid(painter, rect)

        if self._is_empty_slot:
            self._paint_empty_hint(painter, rect)

        painter.setPen(QPen(QColor("#20202b"), 1))
        painter.drawLine(int(rect.left()), int(rect.bottom()), int(rect.right()), int(rect.bottom()))

    def _paint_grid(self, painter: QPainter, rect: QRectF) -> None:
        major = ruler_step_seconds(self._px_per_sec)
        minor = ruler_sub_step_seconds(self._px_per_sec)
        total_width = rect.width()

        if minor is not None:
            t = 0.0
            while t * self._px_per_sec <= total_width:
                is_major = abs(t) < 1e-9 or abs(t / major - round(t / major)) < 1e-6
                if not is_major:
                    x = t * self._px_per_sec
                    painter.setPen(QPen(QColor(35, 35, 48, 50), 1))
                    painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
                t += minor

        t = 0.0
        while t * self._px_per_sec <= total_width:
            x = t * self._px_per_sec
            painter.setPen(QPen(QColor(40, 40, 52, 90), 1))
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
            t += major

    def _paint_empty_hint(self, painter: QPainter, rect: QRectF) -> None:
        inner = rect.adjusted(LANE_STRIPE_WIDTH + 8, 6, -8, -6)
        pen = QPen(QColor(90, 90, 110, 120), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(inner, 6, 6)
        font = QFont("Open Sans", 9)
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QColor("#5c5c6e"))
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, EMPTY_LANE_HINT_GENERIC)
