"""Timeline overview strip — clip blocks + viewport window."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from studio.core.models import Project
from studio.ui.icons.lucide_icons import SCENE_ROLE_ACCENT
from studio.ui.timeline.geometry import MINIMAP_HEIGHT, TRACK_ACCENT, timeline_width_px


class TimelineMinimap(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(MINIMAP_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._project: Project | None = None
        self._scroll_x = 0
        self._viewport_w = 1
        self._dragging = False

    def set_project(self, project: Project) -> None:
        self._project = project
        self.update()

    def set_viewport(self, scroll_x: int, viewport_width: int) -> None:
        self._scroll_x = scroll_x
        self._viewport_w = max(1, viewport_width)
        self.update()

    def _content_width(self) -> float:
        if self._project is None:
            return 1.0
        return timeline_width_px(self._project.duration, self._project.px_per_sec)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#14141b"))
        painter.setPen(QPen(QColor("#20202b")))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        if self._project is None or self._project.px_per_sec <= 0:
            return

        content_w = self._content_width()
        scale = self.width() / content_w if content_w > 0 else 1.0
        px_per_sec = self._project.px_per_sec

        for i, track in enumerate(self._project.tracks):
            lane_h = self.height() / max(1, len(self._project.tracks))
            lane_top = i * lane_h
            if track.scene_role and track.scene_role in SCENE_ROLE_ACCENT:
                accent = QColor(SCENE_ROLE_ACCENT[track.scene_role])
            else:
                accent = QColor(TRACK_ACCENT.get(track.type, "#7c5cff"))
            for clip in track.clips:
                x = clip.start * px_per_sec * scale
                w = max(2.0, clip.duration * px_per_sec * scale)
                block = accent
                block.setAlpha(180)
                painter.fillRect(int(x), int(lane_top + 2), int(w), int(lane_h - 4), block)
                if clip.kind == "playlist" or clip.scene_role:
                    painter.setPen(QPen(QColor("#ffffff"), 1))
                    cx = int(x + w / 2)
                    cy = int(lane_top + lane_h / 2)
                    painter.drawEllipse(cx - 2, cy - 2, 4, 4)

        # Viewport window — only when the project has meaningful width beyond the view
        content_w = self._content_width()
        if content_w > self.width() * 1.05:
            vx = self._scroll_x * scale
            vw = min(self.width(), self._viewport_w * scale)
            painter.setPen(QPen(QColor("#ffd54a"), 1))
            painter.setBrush(QBrush(QColor(255, 213, 74, 30)))
            painter.drawRect(int(vx), 1, int(max(4, vw)), self.height() - 3)

    def _time_at_x(self, x: float) -> float:
        if self._project is None or self._project.px_per_sec <= 0:
            return 0.0
        content_w = self._content_width()
        scale = self.width() / content_w if content_w > 0 else 1.0
        return max(0.0, x / scale / self._project.px_per_sec)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._dragging = True
        self.seek_requested.emit(self._time_at_x(event.position().x()))
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            self.seek_requested.emit(self._time_at_x(event.position().x()))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        event.accept()
