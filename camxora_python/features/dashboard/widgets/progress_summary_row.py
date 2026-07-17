"""Progress summary row — matches HomePage ProgressSummaryRow."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from shared.lib.formatting import format_compact_number, percent_of
from shared.themes.deep_blue import SUBTITLE_LABEL_ID

BAR_COLORS = {
    "violet": "#a78bfa",
    "sky": "#38bdf8",
    "emerald": "#34d399",
}


class ProgressSummaryRow(QFrame):
    def __init__(
        self,
        label: str,
        *,
        bar_color: str = "violet",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._label_key = label.upper()
        self._bar_hex = BAR_COLORS.get(bar_color, BAR_COLORS["violet"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        left = QVBoxLayout()
        left.setSpacing(1)
        self._title = QLabel(self._label_key)
        self._title.setObjectName(SUBTITLE_LABEL_ID)
        left.addWidget(self._title)
        self._amount = QLabel("-- / --")
        left.addWidget(self._amount)
        header.addLayout(left, stretch=1)
        self._percent = QLabel("0%")
        header.addWidget(self._percent, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        self._bar.setStyleSheet(
            "QProgressBar { background-color: rgba(255,255,255,0.1); border: none; border-radius: 3px; }"
            f"QProgressBar::chunk {{ background-color: {self._bar_hex}; border-radius: 3px; }}"
        )
        layout.addWidget(self._bar)

    def set_amounts(self, value: int, total: int) -> None:
        safe_total = max(total, 1)
        pct = percent_of(value, safe_total)
        self._amount.setText(f"{format_compact_number(value)} / {format_compact_number(safe_total)}")
        self._percent.setText(f"{pct}%")
        self._bar.setValue(pct)
