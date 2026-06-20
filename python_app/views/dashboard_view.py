from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QHeaderView, QComboBox, QCheckBox, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QDate, QTime, QSize, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient

from .helpers.style_helper import set_panel_role, set_label_role, render_svg_icon
from .helpers import widget_factory


# ────────────────────────────────────────────────────────────
# Custom Donut Chart Widget
# ────────────────────────────────────────────────────────────
class DonutChart(QWidget):
    """Circular progress ring with center percentage and label below."""

    def __init__(self, label: str = "", color: str = "#7466F1", parent=None):
        super().__init__(parent)
        self._value = 0
        self._label = label
        self._color = QColor(color)
        self.setFixedSize(160, 160)

    def setValue(self, v: int) -> None:
        self._value = max(0, min(100, v))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        pen_width = 10
        margin = pen_width // 2 + 4
        rect = QRectF(margin, margin, size - margin * 2, size - margin * 2)

        # Background ring
        bg_pen = QPen(QColor(255, 255, 255, 20))
        bg_pen.setWidth(pen_width)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Foreground ring
        fg_pen = QPen(self._color)
        fg_pen.setWidth(pen_width)
        fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(fg_pen)
        span = int(-self._value / 100.0 * 360 * 16)
        painter.drawArc(rect, 90 * 16, span)

        # Center percentage text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Open Sans")
        font.setPixelSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._value}%")

        painter.end()


# ────────────────────────────────────────────────────────────
# Custom Line Chart Widget (7-day usage)
# ────────────────────────────────────────────────────────────
class LineChart(QWidget):
    """Multi-series line chart showing 7-day usage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series: dict[str, list[int]] = {}
        self._colors: dict[str, QColor] = {}
        self._labels: list[str] = []
        self.setMinimumHeight(220)

    def setData(self, labels: list[str], series: dict[str, list[int]], colors: dict[str, QColor]):
        self._labels = labels
        self._series = series
        self._colors = colors
        self.update()

    def paintEvent(self, event):
        if not self._series or not self._labels:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_l, margin_r, margin_t, margin_b = 40, 20, 20, 40
        chart_w = w - margin_l - margin_r
        chart_h = h - margin_t - margin_b

        # Find max value
        all_vals = [v for vals in self._series.values() for v in vals]
        max_val = max(all_vals) if all_vals else 1
        max_val = max(max_val, 1)

        # Draw grid lines
        grid_pen = QPen(QColor(255, 255, 255, 15))
        painter.setPen(grid_pen)
        for i in range(5):
            y = margin_t + chart_h * (1 - i / 4)
            painter.drawLine(int(margin_l), int(y), int(w - margin_r), int(y))
            # Y-axis labels
            painter.setPen(QColor(255, 255, 255, 60))
            font = QFont("Open Sans")
            font.setPixelSize(11)
            painter.setFont(font)
            val = int(max_val * i / 4)
            painter.drawText(QRectF(0, y - 8, margin_l - 4, 16), Qt.AlignmentFlag.AlignRight, str(val))
            painter.setPen(grid_pen)

        # Draw X-axis labels
        n = len(self._labels)
        painter.setPen(QColor(255, 255, 255, 60))
        font = QFont("Open Sans")
        font.setPixelSize(11)
        painter.setFont(font)
        for i, lbl in enumerate(self._labels):
            x = margin_l + chart_w * i / max(1, n - 1)
            painter.drawText(QRectF(x - 30, h - margin_b + 8, 60, 20), Qt.AlignmentFlag.AlignCenter, lbl)
        painter.setPen(grid_pen)

        # Draw lines
        for name, vals in self._series.items():
            color = self._colors.get(name, QColor(255, 255, 255))
            pen = QPen(color, 2.5)
            painter.setPen(pen)
            points = []
            for i, v in enumerate(vals):
                x = margin_l + chart_w * i / max(1, n - 1)
                y = margin_t + chart_h * (1 - v / max_val)
                points.append(QPointF(x, y))
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])
            # Draw dots
            for pt in points:
                painter.setBrush(color)
                painter.drawEllipse(pt, 4, 4)

        # Legend at bottom
        legend_y = h - 12
        legend_x = margin_l
        _legend_font = QFont("Open Sans")
        _legend_font.setPixelSize(11)
        painter.setFont(_legend_font)
        for name, color in self._colors.items():
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(legend_x, legend_y), 5, 5)
            painter.setPen(QColor(255, 255, 255, 150))
            painter.drawText(int(legend_x + 10), int(legend_y + 4), name)
            legend_x += painter.fontMetrics().horizontalAdvance(name) + 28

        painter.end()


# ────────────────────────────────────────────────────────────
# Dashboard View
# ────────────────────────────────────────────────────────────
class DashboardViewMixin:
    def _build_dashboard_workspace_page(self) -> QWidget:
        page = QWidget()
        set_panel_role(page, "center")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)

        _icon_cache: dict = {}

        # ── Row 1: 4 stat cards ──
        card_defs = [
            ("credits", "Suno Credit Spent", "#201854", "$"),
            ("songs", "Song Generated", "#1f4361", "music"),
            ("images", "Image Generated", "#174f37", "image"),
            ("mp4", "Video Generated", "#4a382e", "video"),
            ("youtube", "Youtube Uploaded", "#22ac93", "video"),
        ]

        self.dashboard_kpi_labels: dict[str, QLabel] = {}
        cards_row = QHBoxLayout()
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(12)

        for key, title_text, bg_color, icon_or_char in card_defs:
            card = QWidget()
            card.setFixedHeight(90)
            card.setStyleSheet(f"background-color: {bg_color}; border-radius: 12px;")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(12)

            # Icon badge
            icon_badge = QLabel()
            icon_badge.setFixedSize(QSize(40, 40))
            icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_badge.setStyleSheet("background-color: rgba(255,255,255,0.12); border-radius: 20px;")

            if icon_or_char == "$":
                dollar_label = QLabel("$")
                dollar_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 700; background: transparent;")
                dollar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge_layout = QHBoxLayout(icon_badge)
                badge_layout.setContentsMargins(0, 0, 0, 0)
                badge_layout.addWidget(dollar_label)
            else:
                icon_qicon = render_svg_icon(self._lucide_icon_path(icon_or_char), 20, "#ffffff", cache=_icon_cache)
                icon_badge.setPixmap(icon_qicon.pixmap(QSize(20, 20)))

            card_layout.addWidget(icon_badge)

            text_vbox = QVBoxLayout()
            text_vbox.setContentsMargins(0, 0, 0, 0)
            text_vbox.setSpacing(2)

            title_lab = QLabel(title_text)
            title_lab.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 12px; font-weight: 500; background: transparent;")
            text_vbox.addWidget(title_lab)

            value_lab = QLabel("—")
            value_lab.setStyleSheet("color: #ffffff; font-size: 24px; font-weight: 700; background: transparent;")
            text_vbox.addWidget(value_lab)

            card_layout.addLayout(text_vbox, 1)
            self.dashboard_kpi_labels[key] = value_lab
            cards_row.addWidget(card, 1)

        layout.addLayout(cards_row)

        # ── Row 2: donut charts (left, 1/4 width) + line chart (right, 3/4 width) ──
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(12)

        # Donut charts card
        donuts_card = QWidget()
        donuts_card.setStyleSheet("background-color: #081028; border-radius: 12px;")
        donuts_layout = QVBoxLayout(donuts_card)
        donuts_layout.setContentsMargins(16, 14, 16, 14)
        donuts_layout.setSpacing(6)

        donuts_title = QLabel("Resource Remaining")
        donuts_title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px; font-weight: 600; background: transparent;")
        donuts_layout.addWidget(donuts_title)

        donuts_row = QHBoxLayout()
        donuts_row.setContentsMargins(0, 0, 0, 0)
        donuts_row.setSpacing(4)

        self.dashboard_donut_credits = DonutChart("Credits", "#7466F1")
        self.dashboard_donut_songs = DonutChart("Songs", "#1ABCFE")
        self.dashboard_donut_images = DonutChart("Images", "#0ACF83")

        for d in [self.dashboard_donut_credits, self.dashboard_donut_songs, self.dashboard_donut_images]:
            donuts_row.addWidget(d, 0, Qt.AlignmentFlag.AlignHCenter)

        donuts_layout.addLayout(donuts_row)
        row2.addWidget(donuts_card, 1)

        # Line chart card
        chart_card = QWidget()
        chart_card.setStyleSheet("background-color: #081028; border-radius: 12px;")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(16, 14, 16, 14)
        chart_layout.setSpacing(6)

        chart_title = QLabel("Weekly Usage")
        chart_title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px; font-weight: 600; background: transparent;")
        chart_layout.addWidget(chart_title)

        self.dashboard_line_chart = LineChart()
        chart_layout.addWidget(self.dashboard_line_chart, 1)
        row2.addWidget(chart_card, 3)

        layout.addLayout(row2, 1)

        # ── Row 3: Recent Activity table ──
        activity_card = QWidget()
        activity_card.setStyleSheet("background-color: #081028; border-radius: 12px;")
        activity_outer = QVBoxLayout(activity_card)
        activity_outer.setContentsMargins(16, 14, 16, 14)
        activity_outer.setSpacing(8)

        activity_header = QHBoxLayout()
        activity_header.setContentsMargins(0, 0, 0, 0)
        activity_title = QLabel("Recent Activity")
        activity_title.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px; font-weight: 600; background: transparent;")
        activity_header.addWidget(activity_title)
        activity_header.addStretch(1)
        activity_outer.addLayout(activity_header)

        self.dashboard_activity_table = QTableWidget(0, 6)
        self.dashboard_activity_table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: none;
                color: rgba(255,255,255,0.8);
                gridline-color: rgba(255,255,255,0.06);
                font-size: 12px;
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background-color: transparent;
                color: rgba(255,255,255,0.5);
                font-size: 11px;
                font-weight: 600;
                border: none;
                border-bottom: 1px solid rgba(255,255,255,0.08);
                padding: 8px;
            }
        """)
        self.dashboard_activity_table.setHorizontalHeaderLabels(
            ["Time", "Type", "Batch", "Channel", "Stage", "Detail"]
        )
        self.dashboard_activity_table.verticalHeader().setVisible(False)
        self.dashboard_activity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dashboard_activity_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.dashboard_activity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.dashboard_activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dashboard_activity_table.setAlternatingRowColors(True)
        self.dashboard_activity_table.setShowGrid(False)
        self.dashboard_activity_table.verticalHeader().setDefaultSectionSize(40)
        activity_outer.addWidget(self.dashboard_activity_table, 1)

        layout.addWidget(activity_card, 1)

        # ── Hidden refs for controller compatibility ──
        self.dashboard_status_label = QLabel("")
        self.dashboard_status_label.setVisible(False)
        self.dashboard_summary_label = QLabel("")
        self.dashboard_summary_label.setVisible(False)
        self.dashboard_failures_table = QTableWidget(0, 6)
        self.dashboard_failures_table.setVisible(False)
        self.dashboard_stage_bars = {}
        self.dashboard_from_date = widget_factory.create_calendar_picker(lambda: None, self.ui, width=118)
        self.dashboard_from_date.setVisible(False)
        self.dashboard_to_date = widget_factory.create_calendar_picker(lambda: None, self.ui, width=118)
        self.dashboard_to_date.setVisible(False)
        self.dashboard_profile_combo = QComboBox()
        self.dashboard_profile_combo.setVisible(False)
        self.dashboard_active_only = QCheckBox("Active only")
        self.dashboard_active_only.setVisible(False)
        self.dashboard_refresh_button = QPushButton("Refresh")
        self.dashboard_refresh_button.setVisible(False)

        return page
