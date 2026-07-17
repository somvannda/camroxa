"""Metric bar and summary field widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout

from shared.themes.deep_blue import SUBTITLE_LABEL_ID


class SummaryField(QFrame):
    """Label + value field used in profile cards."""

    def __init__(self, label: str, value: str = "--", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title = QLabel(label.upper())
        title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(title)

        self._value = QLabel(value)
        self._value.setWordWrap(True)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class MetricBar(QFrame):
    """Progress bar with label and value."""

    def __init__(
        self,
        label: str,
        value_text: str = "--",
        percent: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self._header = QLabel(f"{label.upper()}  ·  {value_text}")
        self._header.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._header)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(max(0, min(100, percent)))
        self._bar.setTextVisible(True)
        self._bar.setFormat(f"{percent}%")
        layout.addWidget(self._bar)

    def set_values(self, value_text: str, percent: int) -> None:
        clamped = max(0, min(100, percent))
        self._bar.setValue(clamped)
        self._bar.setFormat(f"{clamped}%")
        label_text = self._header.text().split("  ·  ", 1)[0]
        self._header.setText(f"{label_text}  ·  {value_text}")
