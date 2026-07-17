"""Simple usage chart widget for dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from shared.models.platform import DailyUsage
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


def build_polyline_points(
    values: list[int],
    width: float,
    height: float,
    padding: float,
) -> list[tuple[float, float]]:
    if not values:
        return []
    max_value = max(max(values), 1)
    x_step = (width - padding * 2) / max(len(values) - 1, 1)
    points: list[tuple[float, float]] = []
    for index, value in enumerate(values):
        x = padding + index * x_step
        y = height - padding - (value / max_value) * (height - padding * 2)
        points.append((x, y))
    return points


class UsageChartWidget(QFrame):
    """Line chart for songs, images, and videos over recent days."""

    _COLORS = ("#7466F1", "#1ABCFE", "#0ACF83")
    _VIEW_WIDTH = 620.0
    _VIEW_HEIGHT = 240.0
    _PADDING = 20.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboard_chart_canvas")
        self.setMinimumHeight(320)
        self._entries: list[DailyUsage] = []

    def set_entries(self, entries: list[DailyUsage]) -> None:
        self._entries = entries
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        scale_x = rect.width() / self._VIEW_WIDTH
        scale_y = rect.height() / self._VIEW_HEIGHT

        if not self._entries:
            painter.setPen(QPen(QColor("#8aa0b0")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No usage data available yet.")
            return

        dash_pen = QPen(QColor(255, 255, 255, 15), 1, Qt.PenStyle.DashLine)
        for line in range(4):
            y = (20 + line * 50) * scale_y
            painter.setPen(dash_pen)
            painter.drawLine(int(20 * scale_x), int(y), int(600 * scale_x), int(y))

        series = [
            [entry.songs for entry in self._entries],
            [entry.images for entry in self._entries],
            [entry.videos for entry in self._entries],
        ]
        for values, color in zip(series, self._COLORS, strict=True):
            points = build_polyline_points(values, self._VIEW_WIDTH, self._VIEW_HEIGHT, self._PADDING)
            if len(points) < 2:
                continue
            scaled = [(p[0] * scale_x, p[1] * scale_y) for p in points]
            painter.setPen(QPen(QColor(color), 3))
            for start, end in zip(scaled, scaled[1:], strict=False):
                painter.drawLine(int(start[0]), int(start[1]), int(end[0]), int(end[1]))


class UsageLegend(QFrame):
    """Legend labels for the usage chart."""

    def __init__(self, *, horizontal: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12 if horizontal else 4)
        for label, color in zip(("Songs", "Images", "Videos"), UsageChartWidget._COLORS, strict=True):
            text = QLabel(f"● {label}")
            text.setObjectName(SUBTITLE_LABEL_ID)
            text.setStyleSheet(f"color: {color};")
            layout.addWidget(text)
        if horizontal:
            layout.addStretch()
