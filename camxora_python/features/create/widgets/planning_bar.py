"""Compact From/To/Primary/Secondary/Count bar."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSpinBox, QWidget

from features.create.constants import PLANNING_BAR_HEIGHT
from features.create.widgets.studio_controls import StudioComboBox, StudioDateEdit


class PlanningBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlanningBar")
        self.setFixedHeight(PLANNING_BAR_HEIGHT)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(12)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        today = date.today()
        qt_today = QDate(today.year, today.month, today.day)
        self.from_date = self._date(qt_today)
        self.to_date = self._date(qt_today)
        row.addLayout(self._labeled("From", self.from_date))
        row.addLayout(self._labeled("To", self.to_date))

        self.primary = StudioComboBox()
        self.primary.addItems(["English", "Khmer", "German", "Spanish", "French"])
        self.primary.setFixedWidth(128)
        row.addLayout(self._labeled("Primary", self.primary))

        self.secondary = StudioComboBox()
        self.secondary.addItems(["None", "English", "Khmer"])
        self.secondary.setFixedWidth(128)
        row.addLayout(self._labeled("Secondary", self.secondary))

        self.count = QSpinBox()
        self.count.setRange(1, 20)
        self.count.setValue(4)
        self.count.setFixedWidth(64)
        row.addLayout(self._labeled("Count", self.count))
        row.addStretch(1)

    def _date(self, value: QDate) -> StudioDateEdit:
        widget = StudioDateEdit()
        widget.setDate(value)
        widget.setFixedWidth(132)
        return widget

    def _labeled(self, text: str, widget: QWidget) -> QHBoxLayout:
        box = QHBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        box.setAlignment(Qt.AlignmentFlag.AlignLeft)
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        box.addWidget(label)
        box.addWidget(widget)
        return box
