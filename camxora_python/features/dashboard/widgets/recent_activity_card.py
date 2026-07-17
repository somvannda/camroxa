"""Recent activity table with header and status pills."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTableWidgetItem, QVBoxLayout, QWidget

from shared.lib.formatting import format_datetime
from shared.models.platform import DashboardOverview, RecentActivity
from shared.themes.badge_pills import apply_badge_pill, status_pill_object_name
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.data_table import create_data_table

LOADING_MESSAGE = "Loading recent activity..."
EMPTY_MESSAGE = "No recent activity found."
SUBTITLE = "Latest events returned by the dashboard stats API."


class RecentActivityCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel("RECENT ACTIVITY")
        title.setObjectName(SUBTITLE_LABEL_ID)
        left.addWidget(title)
        subtitle = QLabel(SUBTITLE)
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)
        header.addLayout(left, stretch=1)

        right = QVBoxLayout()
        self._plan_line = QLabel("No plan")
        self._plan_line.setObjectName(SUBTITLE_LABEL_ID)
        self._plan_line.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self._plan_line)
        self._expiry_line = QLabel("Expires: Not provided")
        self._expiry_line.setObjectName(SUBTITLE_LABEL_ID)
        self._expiry_line.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self._expiry_line)
        header.addLayout(right)
        root.addLayout(header)

        self._table = create_data_table(
            ["Time", "Type", "Batch", "Channel", "Stage", "Detail"]
        )
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
        self._table.clearSpans()
        self._table.setRowCount(len(activities))
        for row_index, activity in enumerate(activities):
            values = [
                format_datetime(activity.timestamp),
                activity.kind,
                "--",
                "--",
                activity.status,
                activity.detail,
            ]
            for col_index, value in enumerate(values):
                if col_index == 4:
                    pill = QLabel()
                    apply_badge_pill(pill, status_pill_object_name(value), label=value)
                    pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self._table.setCellWidget(row_index, col_index, pill)
                else:
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self._table.setItem(row_index, col_index, item)

    def apply_overview(self, data: DashboardOverview) -> None:
        plan = data.license.plan_type if data.license else data.me.plan_name or "No plan"
        if data.license and data.license.expiration_date:
            expiry = f"Expires: {format_datetime(data.license.expiration_date)}"
        else:
            expiry = "Expires: Not provided"
        self.set_header_plan(plan, expiry)
        self.set_activities(data.stats.recent_activity)

    def _set_message(self, message: str) -> None:
        self._table.clearSpans()
        self._table.setRowCount(1)
        self._table.setSpan(0, 0, 1, 6)
        for col in range(6):
            self._table.setCellWidget(0, col, None)
        item = QTableWidgetItem(message)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 0, item)
