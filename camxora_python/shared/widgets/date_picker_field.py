"""Compact date trigger — matches DatePickerField.tsx (no visible label, h-9, 132px)."""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from shared.widgets.shell_date_edit import ShellDateEdit


class DatePickerField(QWidget):
    value_changed = Signal(str)

    def __init__(self, label: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._edit = ShellDateEdit()
        self._edit.setFixedSize(132, 32)
        self._edit.setObjectName("workflow_date_edit")
        self._edit.setAccessibleName(label)
        self._edit.setToolTip(label)
        layout.addWidget(self._edit)
        self._edit.dateChanged.connect(lambda *_: self.value_changed.emit(self.value()))

    def set_value(self, ymd: str) -> None:
        parsed = QDate.fromString(ymd, "yyyy-MM-dd")
        if parsed.isValid():
            self._edit.setDate(parsed)

    def value(self) -> str:
        return self._edit.date().toString("yyyy-MM-dd")
