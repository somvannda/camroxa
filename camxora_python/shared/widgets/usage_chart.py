"""Lightweight weekly usage chart (custom QPainter + pixmap cache).

Qt Charts (QSplineSeries + animations) was too heavy for the dashboard scroll
area and made the whole desktop shell feel sticky. This painter path keeps the
soft curves without a live chart scene.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from shared.models.platform import DailyUsage
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


def build_polyline_points(
    values: list[int],
    width: float,
    height: float,
    padding: float,
) -> list[tuple[float, float]]:
    """Map series values into chart coordinates (unit tests / callers)."""
    if not values:
        return []
    max_value = max(max(values), 1)
    x_step = (width - padding * 2) / max(len(values) - 1, 1)
    points: list[tuple[float, float]] = []
    for index, value in enumerate(values):
        x = padding + index * x_step
        y = height - padding - (max(value, 0) / max_value) * (height - padding * 2)
        points.append((x, y))
    return points


def build_soft_curve_path(points: list[tuple[float, float]]) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(points[0][0], points[0][1])
    if len(points) == 1:
        return path
    if len(points) == 2:
        path.lineTo(points[1][0], points[1][1])
        return path
    for index in range(len(points) - 1):
        p1 = points[index]
        p2 = points[index + 1]
        dx = (p2[0] - p1[0]) * 0.18
        path.cubicTo(p1[0] + dx, p1[1], p2[0] - dx, p2[1], p2[0], p2[1])
    return path


def _series_for_entry(entry: DailyUsage) -> tuple[int, int, int, int, int]:
    studio = entry.studio_exports if (entry.studio_exports or entry.manual_exports) else entry.videos
    return (
        max(0, int(entry.songs)),
        max(0, int(entry.images)),
        max(0, int(studio)),
        max(0, int(entry.manual_exports)),
        max(0, int(entry.youtube_uploads)),
    )


def _entries_fingerprint(entries: list[DailyUsage]) -> tuple:
    return tuple(
        (
            entry.date,
            entry.songs,
            entry.images,
            entry.videos,
            entry.studio_exports,
            entry.manual_exports,
            entry.youtube_uploads,
        )
        for entry in entries
    )


class UsageChartWidget(QFrame):
    """Soft-curve usage chart with pixmap cache for cheap scroll/repaint."""

    _SERIES = (
        ("Songs", "#7466F1"),
        ("Images", "#1ABCFE"),
        ("Studio exports", "#0ACF83"),
        ("Manual exports", "#F59E0B"),
        ("YouTube uploads", "#EF4444"),
    )
    _PAD_L = 36.0
    _PAD_R = 12.0
    _PAD_T = 16.0
    _PAD_B = 12.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboard_chart_canvas")
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self._entries: list[DailyUsage] = []
        self._fingerprint: tuple = ()
        self._cache: QPixmap | None = None
        self._cache_key: tuple[int, int, tuple] | None = None

    def set_entries(self, entries: list[DailyUsage]) -> None:
        fingerprint = _entries_fingerprint(entries)
        if fingerprint == self._fingerprint:
            return
        self._entries = list(entries)
        self._fingerprint = fingerprint
        self._cache = None
        self._cache_key = None
        self.update()

    def active_series_mask(self) -> list[bool]:
        totals = [0, 0, 0, 0, 0]
        for entry in self._entries:
            values = _series_for_entry(entry)
            for i, value in enumerate(values):
                totals[i] += value
        return [total > 0 for total in totals]

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._cache = None
        self._cache_key = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().paintEvent(event)
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        key = (width, height, self._fingerprint)
        if self._cache is None or self._cache_key != key:
            dpr = max(float(self.devicePixelRatioF()), 1.0)
            pixmap = QPixmap(int(width * dpr), int(height * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._paint_chart(painter, float(width), float(height))
            painter.end()
            self._cache = pixmap
            self._cache_key = key

        out = QPainter(self)
        out.drawPixmap(0, 0, self._cache)
        out.end()

    def _paint_chart(self, painter: QPainter, width: float, height: float) -> None:
        if not self._entries:
            painter.setPen(QPen(QColor("#8aa0b0")))
            font = QFont("Open Sans")
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, 0, width, height),
                int(Qt.AlignmentFlag.AlignCenter),
                "No usage data available yet.",
            )
            return

        plot_w = max(width - self._PAD_L - self._PAD_R, 1.0)
        plot_h = max(height - self._PAD_T - self._PAD_B, 1.0)
        left = self._PAD_L
        top = self._PAD_T
        bottom = top + plot_h

        active = self.active_series_mask()
        series_values = [
            [row[i] for row in (_series_for_entry(entry) for entry in self._entries)]
            for i in range(5)
        ]
        peak = max(
            (max(values) for values, is_on in zip(series_values, active, strict=True) if is_on),
            default=1,
        )
        peak = max(int(peak), 1)

        grid_pen = QPen(QColor(255, 255, 255, 22), 1.0)
        label_pen = QPen(QColor("#8aa0b0"))
        label_font = QFont("Open Sans")
        label_font.setPixelSize(11)
        painter.setFont(label_font)

        for step in range(5):
            frac = step / 4.0
            y = bottom - frac * plot_h
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(left, y), QPointF(left + plot_w, y))
            if step > 0 or peak > 1:
                value = int(round(peak * frac))
                painter.setPen(label_pen)
                painter.drawText(
                    QRectF(0, y - 8, left - 6, 16),
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    str(value),
                )

        n = len(self._entries)
        x_step = plot_w / max(n - 1, 1)

        for series_index, (_name, color_hex) in enumerate(self._SERIES):
            if not active[series_index]:
                continue
            values = series_values[series_index]
            points: list[tuple[float, float]] = []
            for index, value in enumerate(values):
                x = left + index * x_step
                y = bottom - (max(value, 0) / peak) * plot_h
                points.append((x, y))
            color = QColor(color_hex)
            pen = QPen(color, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(build_soft_curve_path(points))
            # Small dots only — cheap and readable for 7 points
            painter.setBrush(color)
            for x, y in points:
                painter.drawEllipse(QPointF(x, y), 3.2, 3.2)


class UsageLegend(QFrame):
    """Legend labels for the usage chart; dims series with zero activity."""

    def __init__(self, *, horizontal: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: list[QLabel] = []
        layout = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12 if horizontal else 4)
        for label, color in UsageChartWidget._SERIES:
            text = QLabel(f"● {label}")
            text.setObjectName(SUBTITLE_LABEL_ID)
            text.setStyleSheet(f"color: {color};")
            layout.addWidget(text)
            self._labels.append(text)
        if horizontal:
            layout.addStretch()

    def set_active_mask(self, mask: list[bool]) -> None:
        for index, label_widget in enumerate(self._labels):
            name, color = UsageChartWidget._SERIES[index]
            active = bool(mask[index]) if index < len(mask) else False
            if active:
                label_widget.setText(f"● {name}")
                label_widget.setStyleSheet(f"color: {color};")
            else:
                label_widget.setText(f"○ {name} (0)")
                label_widget.setStyleSheet("color: #5b6b7c;")
