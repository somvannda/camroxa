"""Membership metric bar — matches ProfilePage.tsx MetricBar (not ProgressSummaryRow)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID

BAR_COLORS = {
    "emerald": "#34d399",
    "sky": "#38bdf8",
}


class MembershipMetricBar(QFrame):
    """Label + value on one row, progress bar below."""

    def __init__(
        self,
        label: str,
        *,
        bar_color: str = "emerald",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self._bar_hex = BAR_COLORS.get(bar_color, BAR_COLORS["emerald"])

        layout = QVBoxLayout(self)
        # Compact membership meters (tighter than Account summary tiles).
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        header = QHBoxLayout()
        self._label = QLabel(label.upper())
        self._label.setObjectName(SUBTITLE_LABEL_ID)
        header.addWidget(self._label)
        header.addStretch()
        self._value = QLabel("--")
        header.addWidget(self._value, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(
            "QProgressBar { background-color: rgba(255,255,255,0.1); border: none; border-radius: 4px; }"
            f"QProgressBar::chunk {{ background-color: {self._bar_hex}; border-radius: 4px; }}"
        )
        layout.addWidget(self._bar)

    def set_metric(self, value_text: str, percent: int) -> None:
        self._value.setText(value_text)
        self._bar.setValue(max(0, min(100, percent)))
