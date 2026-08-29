"""Weekly usage card with Create studio chrome."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from features.dashboard.widgets.remaining_month_card import NestedPanel
from shared.lib.ui_font import studio_font
from shared.models.platform import DailyUsage
from shared.widgets.usage_chart import UsageChartWidget, UsageLegend


def _usage_fingerprint(entries: list[DailyUsage]) -> tuple:
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


class WeeklyUsageCard(StudioPanel):
    SUBTITLE = (
        "7-day overview: Songs · Images · Studio exports (pipeline) · "
        "Manual exports (notes page) · YouTube uploads."
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._usage_fingerprint: tuple = ()
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(16)
        header.setContentsMargins(0, 0, 0, 4)
        left = QVBoxLayout()
        left.setSpacing(4)
        title = QLabel("WEEKLY USAGE")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        left.addWidget(title)
        subtitle = QLabel(self.SUBTITLE)
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)
        header.addLayout(left, 1)

        self._plan_badge = NestedPanel()
        self._plan_badge.setMinimumWidth(148)
        self._plan_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        badge_layout = QVBoxLayout(self._plan_badge)
        badge_layout.setContentsMargins(10, 8, 10, 8)
        badge_layout.setSpacing(2)
        badge_label = QLabel("CURRENT PLAN")
        badge_label.setObjectName("FieldLabel")
        badge_label.setFont(studio_font(10))
        badge_layout.addWidget(badge_label)
        self._plan_value = QLabel("No plan")
        self._plan_value.setObjectName("PageSubtitle")
        badge_layout.addWidget(self._plan_value)
        self._plan_expiry = QLabel("Expiration not provided")
        self._plan_expiry.setObjectName("FieldLabel")
        badge_layout.addWidget(self._plan_expiry)
        header.addWidget(self._plan_badge, 0)
        root.addLayout(header)

        self._chart = UsageChartWidget()
        self._chart.setMinimumHeight(220)
        self._chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._chart, 1)
        self._empty_days = QLabel("No usage data available yet.")
        self._empty_days.setObjectName("PageSubtitle")
        self._empty_days.hide()
        root.addWidget(self._empty_days)
        self._legend = UsageLegend(horizontal=True)
        root.addWidget(self._legend)

    def set_plan(self, plan_type: str, expiry_text: str) -> None:
        self._plan_value.setText(plan_type or "No plan")
        self._plan_expiry.setText(expiry_text or "Expiration not provided")

    def set_usage(self, entries: list[DailyUsage]) -> None:
        fingerprint = _usage_fingerprint(entries)
        if fingerprint == self._usage_fingerprint:
            return
        self._usage_fingerprint = fingerprint
        self._chart.set_entries(entries)
        self._legend.set_active_mask(self._chart.active_series_mask())
        self._empty_days.hide()
