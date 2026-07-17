"""Weekly usage card with chart, plan badge, day grid, legend."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from shared.lib.formatting import format_short_date
from shared.models.platform import DailyUsage
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.usage_chart import UsageChartWidget, UsageLegend


class WeeklyUsageCard(QFrame):
    SUBTITLE = "Songs, images, and videos generated over the recent 7-day window."

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        left = QVBoxLayout()
        title = QLabel("WEEKLY USAGE")
        title.setObjectName(SUBTITLE_LABEL_ID)
        left.addWidget(title)
        subtitle = QLabel(self.SUBTITLE)
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)
        header.addLayout(left, stretch=1)

        self._plan_badge = QFrame()
        self._plan_badge.setObjectName("dashboard_plan_badge")
        badge_layout = QVBoxLayout(self._plan_badge)
        badge_layout.setContentsMargins(12, 10, 12, 10)
        badge_layout.setSpacing(2)
        badge_label = QLabel("CURRENT PLAN")
        badge_label.setObjectName(SUBTITLE_LABEL_ID)
        badge_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        badge_layout.addWidget(badge_label)
        self._plan_value = QLabel("No plan")
        self._plan_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        badge_layout.addWidget(self._plan_value)
        self._plan_expiry = QLabel("Expiration not provided")
        self._plan_expiry.setObjectName(SUBTITLE_LABEL_ID)
        self._plan_expiry.setAlignment(Qt.AlignmentFlag.AlignRight)
        badge_layout.addWidget(self._plan_expiry)
        header.addWidget(self._plan_badge)
        root.addLayout(header)

        chart_panel = QFrame()
        chart_panel.setObjectName("dashboard_chart_panel")
        chart_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(12, 12, 12, 12)
        chart_layout.setSpacing(8)
        self._chart = UsageChartWidget()
        self._chart.setMinimumHeight(320)
        self._chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_layout.addWidget(self._chart, stretch=1)
        self._day_grid_host = QWidget()
        self._day_grid_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._day_grid = QHBoxLayout(self._day_grid_host)
        self._day_grid.setContentsMargins(0, 0, 0, 0)
        self._day_grid.setSpacing(8)
        chart_layout.addWidget(self._day_grid_host)
        self._empty_days = QLabel("No usage data available yet.")
        self._empty_days.setObjectName(SUBTITLE_LABEL_ID)
        self._empty_days.hide()
        chart_layout.addWidget(self._empty_days)
        legend = UsageLegend(horizontal=True)
        chart_layout.addWidget(legend)
        root.addWidget(chart_panel, stretch=1)

    def set_plan(self, plan_type: str, expiry_text: str) -> None:
        self._plan_value.setText(plan_type)
        self._plan_expiry.setText(expiry_text)

    def set_usage(self, entries: list[DailyUsage]) -> None:
        self._chart.set_entries(entries)
        self._clear_day_grid()
        if not entries:
            self._empty_days.show()
            return
        self._empty_days.hide()
        for entry in entries:
            col = QVBoxLayout()
            col.setSpacing(2)
            date_label = QLabel(format_short_date(entry.date))
            date_label.setObjectName(SUBTITLE_LABEL_ID)
            date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(date_label)
            total = entry.songs + entry.images + entry.videos
            count_label = QLabel(f"{total} items")
            count_label.setObjectName(SUBTITLE_LABEL_ID)
            count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(count_label)
            cell = QWidget()
            cell.setLayout(col)
            self._day_grid.addWidget(cell, stretch=1)

    def _clear_day_grid(self) -> None:
        while self._day_grid.count():
            item = self._day_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
