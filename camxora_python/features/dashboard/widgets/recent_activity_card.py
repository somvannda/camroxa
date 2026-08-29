"""Recent activity table with Create studio chrome."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTableWidgetItem, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from shared.lib.formatting import format_datetime
from shared.lib.ui_font import studio_font
from shared.models.platform import DashboardOverview, RecentActivity
from shared.widgets.data_table import create_data_table

LOADING_MESSAGE = "Loading recent activity..."
EMPTY_MESSAGE = "No recent activity found."
SUBTITLE = "Latest events returned by the dashboard stats API."
HEADERS = ["Time", "Type", "Batch", "Channel", "Stage", "Detail", "Status"]
STATUS_COL = 6


class RecentActivityCard(StudioPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel("RECENT ACTIVITY")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        left.addWidget(title)
        subtitle = QLabel(SUBTITLE)
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)
        header.addLayout(left, stretch=1)

        right = QVBoxLayout()
        self._plan_line = QLabel("No plan")
        self._plan_line.setObjectName("PageSubtitle")
        self._plan_line.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self._plan_line)
        self._expiry_line = QLabel("Expires: Not provided")
        self._expiry_line.setObjectName("FieldLabel")
        self._expiry_line.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self._expiry_line)
        header.addLayout(right)
        root.addLayout(header)

        self._table = create_data_table(HEADERS)
        self._table.setObjectName("ActivityTable")
        self._table.setSortingEnabled(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.setMinimumHeight(160)
        root.addWidget(self._table)

    def set_header_plan(self, plan_type: str, expiry_text: str) -> None:
        self._plan_line.setText(plan_type)
        self._expiry_line.setText(expiry_text)

    def show_loading(self) -> None:
        self._set_message(LOADING_MESSAGE)

    def show_empty(self) -> None:
        self._set_message(EMPTY_MESSAGE)

    def set_activities(self, activities: list[RecentActivity]) -> None:
        if not activities:
            self.show_empty()
            return
        sorting = self._table.isSortingEnabled()
        self._table.setSortingEnabled(False)
        self._table.clearSpans()
        self._table.setRowCount(len(activities))
        for row_index, activity in enumerate(activities):
            values = [
                format_datetime(activity.timestamp),
                activity.kind,
                "--",
                "--",
                "--",
                activity.detail,
                activity.status,
            ]
            for col_index, value in enumerate(values):
                self._table.setCellWidget(row_index, col_index, None)
                if col_index == STATUS_COL:
                    pill = QLabel(value)
                    pill.setObjectName("StatusBadge")
                    pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self._table.setCellWidget(row_index, col_index, pill)
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self._table.setItem(row_index, col_index, item)
                else:
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self._table.setItem(row_index, col_index, item)
        self._table.setSortingEnabled(sorting)

    def apply_overview(self, data: DashboardOverview) -> None:
        plan = data.license.plan_type if data.license else data.me.plan_name or "No plan"
        if data.license and data.license.expiration_date:
            expiry = f"Expires: {format_datetime(data.license.expiration_date)}"
        else:
            expiry = "Expires: Not provided"
        self.set_header_plan(plan, expiry)
        self.set_activities(data.stats.recent_activity)

    def _set_message(self, message: str) -> None:
        self._table.setSortingEnabled(False)
        self._table.clearSpans()
        self._table.setRowCount(1)
        self._table.setSpan(0, 0, 1, len(HEADERS))
        for col in range(len(HEADERS)):
            self._table.setCellWidget(0, col, None)
            self._table.setItem(0, col, None)
        item = QTableWidgetItem(message)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 0, item)
