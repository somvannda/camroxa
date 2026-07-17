"""Workflow summary stat cards row — four StatCards, no wrapper card."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from shared.widgets.stat_card import StatCard


class WorkflowStatsRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._runs_card = StatCard("Runs", "0")
        self._active_card = StatCard("Active", "0")
        self._attention_card = StatCard("Need Attention", "0")
        self._done_card = StatCard("Done", "0")
        for card in (
            self._runs_card,
            self._active_card,
            self._attention_card,
            self._done_card,
        ):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(card)

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
