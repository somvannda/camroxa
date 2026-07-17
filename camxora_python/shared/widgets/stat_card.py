"""Reusable stat card widget."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class StatCard(QFrame):
    """KPI card with title and large value."""

    def __init__(
        self,
        title: str,
        value: str = "--",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._title = QLabel(title.upper())
        self._title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._title)

        self._value = QLabel(value)
        self._value.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)
