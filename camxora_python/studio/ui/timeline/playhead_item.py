"""Playhead line + draggable scene handle."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject, QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem, QWidget

PLAYHEAD_COLOR = QColor("#ff5470")
HEAD_HALF_WIDTH = 7
HEAD_HEIGHT = 10
HIT_WIDTH = 14


class PlayheadItem(QGraphicsObject):
    seek_requested = Signal(float)

    def __init__(self, px_per_sec: float, height: float, parent=None) -> None:
        super().__init__(parent)
        self._px_per_sec = px_per_sec
        self._scene_height = height
        self._time = 0.0
        self._dragging = False
        self.setZValue(25)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def set_time(self, time: float) -> None:
        self._time = max(0.0, time)
        self.setPos(self._time * self._px_per_sec, 0)
        self.update()

    def set_scene_height(self, height: float) -> None:
        self._scene_height = height
        self.update()

    def set_px_per_sec(self, px_per_sec: float) -> None:
        self._px_per_sec = px_per_sec
        self.set_time(self._time)

    def time(self) -> float:
        return self._time

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-HIT_WIDTH / 2, 0, HIT_WIDTH, self._scene_height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:  # noqa: N802
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx = 0.0
        painter.setPen(QPen(PLAYHEAD_COLOR, 2))
        painter.drawLine(QPointF(cx, HEAD_HEIGHT), QPointF(cx, self._scene_height))
        head = [
            QPointF(cx, 0),
            QPointF(cx - HEAD_HALF_WIDTH, HEAD_HEIGHT),
            QPointF(cx + HEAD_HALF_WIDTH, HEAD_HEIGHT),
        ]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(PLAYHEAD_COLOR))
        painter.drawPolygon(head)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if not self._dragging or self._px_per_sec <= 0:
            return
        scene_x = event.scenePos().x()
        self._time = max(0.0, scene_x / self._px_per_sec)
        self.setPos(self._time * self._px_per_sec, 0)
        self.seek_requested.emit(self._time)
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._dragging = False
            self.seek_requested.emit(self._time)
            event.accept()
            return
        super().mouseReleaseEvent(event)
