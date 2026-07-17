"""Progress summary stat cards row — four StatCards, no wrapper card."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from shared.widgets.stat_card import StatCard


class ProgressStatsRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._active_card = StatCard("Active Runs", "0")
        self._converter_card = StatCard("Converter / Merger", "0")
        self._waiting_card = StatCard("Waiting On User", "0")
        self._failed_card = StatCard("Failed / Blocked", "0")
        for card in (
            self._active_card,
            self._converter_card,
            self._waiting_card,
            self._failed_card,
        ):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(card)

    def set_summary_counts(
        self,
        *,
        active: int,
        converter: int,
        waiting: int,
        failed: int,
    ) -> None:
        self._active_card.set_value(str(active))
        self._converter_card.set_value(str(converter))
        self._waiting_card.set_value(str(waiting))
        self._failed_card.set_value(str(failed))
