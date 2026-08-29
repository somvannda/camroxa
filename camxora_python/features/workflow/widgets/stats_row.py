"""Workflow summary stat cards — Create studio KPI chrome."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from shared.lib.ui_font import studio_font


class WorkflowStatCard(StudioPanel):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(72)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("FieldLabel")
        label.setFont(studio_font(11))
        root.addWidget(label)
        self._value = QLabel("0")
        self._value.setObjectName("KpiValue")
        self._value.setFont(studio_font(20))
        root.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class WorkflowStatsRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._runs_card = WorkflowStatCard("Runs")
        self._active_card = WorkflowStatCard("Active")
        self._attention_card = WorkflowStatCard("Need Attention")
        self._done_card = WorkflowStatCard("Done")
        for card in (
            self._runs_card,
            self._active_card,
            self._attention_card,
            self._done_card,
        ):
            layout.addWidget(card, stretch=1)

    def set_summary_counts(
        self,
        *,
        runs: int,
        active: int,
        attention: int,
        done: int,
    ) -> None:
        self._runs_card.set_value(str(runs))
        self._active_card.set_value(str(active))
        self._attention_card.set_value(str(attention))
        self._done_card.set_value(str(done))
