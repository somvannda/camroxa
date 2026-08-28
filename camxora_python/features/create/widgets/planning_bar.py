"""Compact From/To/Primary/Secondary/Count bar."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSpinBox, QWidget

from features.create.constants import PLANNING_BAR_HEIGHT
from features.create.widgets.studio_controls import StudioComboBox, StudioDateEdit


class PlanningBar(QFrame):
    changed = Signal()

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
        self.primary.setFixedWidth(128)
        row.addLayout(self._labeled("Primary", self.primary))

        self.secondary = StudioComboBox()
        self.secondary.setFixedWidth(128)
        row.addLayout(self._labeled("Secondary", self.secondary))
        self.set_language_options([("en", "English")])

        self.count = QSpinBox()
        self.count.setRange(1, 50)
        self.count.setValue(4)
        self.count.setFixedWidth(64)
        row.addLayout(self._labeled("Count", self.count))
        row.addStretch(1)

        self.from_date.dateChanged.connect(self.changed.emit)
        self.to_date.dateChanged.connect(self.changed.emit)
        self.primary.currentIndexChanged.connect(self._on_primary_changed)
        self.secondary.currentIndexChanged.connect(self.changed.emit)
        self.count.valueChanged.connect(self.changed.emit)

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

    def set_language_options(self, options: list[tuple[str, str]]) -> None:
        cleaned = [(code.strip(), label.strip()) for code, label in options if code and label]
        if not cleaned:
            cleaned = [("en", "English")]
        primary = str(self.primary.currentData() or cleaned[0][0])
        secondary = str(self.secondary.currentData() or "")
        self.primary.blockSignals(True)
        self.primary.clear()
        for code, label in cleaned:
            self.primary.addItem(label, code)
        index = self.primary.findData(primary)
        self.primary.setCurrentIndex(index if index >= 0 else 0)
        self.primary.blockSignals(False)
        self._refresh_secondary(secondary)
        self.changed.emit()

    def _on_primary_changed(self) -> None:
        self._refresh_secondary(str(self.secondary.currentData() or ""))
        self.changed.emit()

    def _refresh_secondary(self, selected: str = "") -> None:
        primary = str(self.primary.currentData() or "")
        self.secondary.blockSignals(True)
        self.secondary.clear()
        self.secondary.addItem("None", "")
        for index in range(self.primary.count()):
            code = str(self.primary.itemData(index) or "")
            label = self.primary.itemText(index)
            if code and code != primary:
                self.secondary.addItem(label, code)
        index = self.secondary.findData(selected)
        self.secondary.setCurrentIndex(index if index >= 0 else 0)
        self.secondary.blockSignals(False)

    def values(self) -> dict[str, str | int]:
        return {
            "from_date": self.from_date.date().toString("yyyy-MM-dd"),
            "to_date": self.to_date.date().toString("yyyy-MM-dd"),
            "language": str(self.primary.currentData() or "en"),
            "secondary_language": str(self.secondary.currentData() or ""),
            "song_count": int(self.count.value()),
        }
