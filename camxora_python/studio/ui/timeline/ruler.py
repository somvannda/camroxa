"""Timeline ruler — ticks + click/drag scrub, playhead head + time tooltip."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from studio.core.models import Project
from studio.core.time_utils import fmt_time, fmt_time_ruler
from studio.ui.timeline.geometry import (
    RULER_HEIGHT,
    effective_timeline_width_px,
    ruler_step_seconds,
    ruler_sub_step_seconds,
)

_PLAYHEAD_COLOR = QColor("#ff5470")
_INOUT_FILL = QColor(124, 92, 255, 35)


class TimelineRuler(QWidget):
    seek_requested = Signal(float)
    playhead_dragged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(RULER_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._project: Project | None = None
        self._duration = 0.0
        self._px_per_sec = 70.0
        self._scroll_x = 0
        self._playhead_time = 0.0
        self._dragging = False
        self._scrub_label_time: float | None = None

    def set_project(self, project: Project) -> None:
        self._project = project
        self._duration = project.duration
        self._px_per_sec = project.px_per_sec
        self.update()

    def set_scroll_x(self, x: int) -> None:
        self._scroll_x = x
        self.update()

    def set_params(self, duration: float, px_per_sec: float) -> None:
        self._duration = duration
        self._px_per_sec = px_per_sec
        self.update()

    def set_playhead_time(self, time: float) -> None:
        self._playhead_time = max(0.0, time)
        self.update()

    def _time_at_widget_x(self, x: float) -> float:
        if self._px_per_sec <= 0:
            return 0.0
        return max(0.0, (x + self._scroll_x) / self._px_per_sec)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1b1b25"))
        painter.setPen(QColor("#20202b"))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        if self._px_per_sec <= 0:
            return

        view_w = self.width()
        total_width = effective_timeline_width_px(self._duration, self._px_per_sec, view_w)
        font = QFont("Open Sans", 9)
        font.setPixelSize(9)
        painter.setFont(font)

        self._paint_in_out_region(painter, view_w)
        self._paint_markers(painter, view_w)
        self._paint_ticks(painter, total_width, view_w)

        ph_x = self._playhead_time * self._px_per_sec - self._scroll_x
        if -20 <= ph_x <= view_w + 20:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(_PLAYHEAD_COLOR, 2))
            painter.drawLine(int(ph_x), 12, int(ph_x), self.height())
            head = [
                QPointF(ph_x, 2),
                QPointF(ph_x - 7, 12),
                QPointF(ph_x + 7, 12),
            ]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(_PLAYHEAD_COLOR))
            painter.drawPolygon(head)

        if self._scrub_label_time is not None:
            pill_x = self._scrub_label_time * self._px_per_sec - self._scroll_x
            if -60 <= pill_x <= view_w + 60:
                self._paint_time_pill(painter, pill_x, self._scrub_label_time)

    def _paint_in_out_region(self, painter: QPainter, view_w: int) -> None:
        if self._project is None:
            return
        in_pt = self._project.in_point
        out_pt = self._project.out_point
        if in_pt is None and out_pt is None:
            return
        start = float(in_pt) if in_pt is not None else 0.0
        end = float(out_pt) if out_pt is not None else self._duration
        x0 = start * self._px_per_sec - self._scroll_x
        x1 = end * self._px_per_sec - self._scroll_x
        painter.fillRect(int(x0), 0, int(x1 - x0), self.height(), _INOUT_FILL)

    def _paint_markers(self, painter: QPainter, view_w: int) -> None:
        if self._project is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for marker in self._project.markers:
            x = marker.time * self._px_per_sec - self._scroll_x
            if -20 <= x <= view_w + 20:
                diamond = [
                    QPointF(x, 4),
                    QPointF(x + 5, 9),
                    QPointF(x, 14),
                    QPointF(x - 5, 9),
                ]
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor("#ffd54a")))
                painter.drawPolygon(diamond)

    def _paint_ticks(self, painter: QPainter, total_width: float, view_w: int) -> None:
        major = ruler_step_seconds(self._px_per_sec)
        minor = ruler_sub_step_seconds(
            self._px_per_sec,
            self._project.snap_settings.frame_rate if self._project is not None else 30.0,
        )

        if minor is not None:
            t = 0.0
            while t * self._px_per_sec < total_width:
                is_major = abs(t) < 1e-9 or abs(t / major - round(t / major)) < 1e-6
                if not is_major:
                    x = t * self._px_per_sec - self._scroll_x
                    if -20 <= x <= view_w + 20:
                        painter.setPen(QColor("#2a2a36"))
                        painter.drawLine(int(x), 16, int(x), self.height() - 2)
                t += minor

        t = 0.0
        while t * self._px_per_sec < total_width:
            x = t * self._px_per_sec - self._scroll_x
            if -20 <= x <= view_w + 20:
                painter.setPen(QColor("#33333f"))
                painter.drawLine(int(x), 10, int(x), self.height() - 2)
                painter.setPen(QColor("#8b8b9e"))
                painter.drawText(int(x) + 4, 18, fmt_time_ruler(t))
            t += major

    def _paint_time_pill(self, painter: QPainter, x: float, time: float) -> None:
        text = fmt_time(time)
        font = QFont("Open Sans", 9)
        font.setBold(True)
        font.setPixelSize(10)
        painter.setFont(font)
        tw = painter.fontMetrics().horizontalAdvance(text) + 12
        pill = QRectF(x - tw / 2, self.height() - 14, tw, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 84, 112, 220)))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._px_per_sec <= 0:
            return
        self._dragging = True
        t = self._time_at_widget_x(event.position().x())
        self._playhead_time = t
        self._scrub_label_time = t
        self.playhead_dragged.emit(t)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._px_per_sec <= 0:
            return
        t = self._time_at_widget_x(event.position().x())
        if self._dragging:
            self._playhead_time = t
            self._scrub_label_time = t
            self.playhead_dragged.emit(t)
            self.update()
        else:
            QToolTip.showText(event.globalPosition().toPoint(), fmt_time(t), self)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._dragging and self._px_per_sec > 0:
            t = self._time_at_widget_x(event.position().x())
            self._playhead_time = t
            self._scrub_label_time = None
            self.seek_requested.emit(t)
            self._dragging = False
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)
