"""Usage meter row — Create progress-bar style."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from shared.lib.formatting import format_compact_number, percent_of
from shared.lib.ui_font import studio_font

BAR_COLORS = {
    "violet": "#7C3AED",
    "sky": "#38BDF8",
    "emerald": "#00C878",
    "amber": "#F59E0B",
    "rose": "#EC4899",
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
        self.setObjectName("TransparentBlock")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._bar_hex = BAR_COLORS.get(bar_color, BAR_COLORS["violet"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        left = QVBoxLayout()
        left.setSpacing(1)
        self._title = QLabel(label.upper())
        self._title.setObjectName("FieldLabel")
        self._title.setFont(studio_font(10))
        left.addWidget(self._title)
        self._amount = QLabel("-- / --")
        self._amount.setObjectName("PageSubtitle")
        self._amount.setFont(studio_font(12))
        left.addWidget(self._amount)
        header.addLayout(left, 1)
        self._percent = QLabel("0%")
        self._percent.setObjectName("FieldLabel")
        header.addWidget(self._percent)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        self._bar.setStyleSheet(
            "QProgressBar { background-color: #18304A; border: none; border-radius: 2px; }"
            f"QProgressBar::chunk {{ background-color: {self._bar_hex}; border-radius: 2px; }}"
        )
        layout.addWidget(self._bar)

    def set_amounts(self, value: int, total: int) -> None:
        safe_total = max(int(total), 0)
        used = max(int(value), 0)
        if safe_total <= 0:
            self.set_unmetered()
            return
        pct = percent_of(used, safe_total)
        self._amount.setText(f"{format_compact_number(used)} / {format_compact_number(safe_total)}")
        self._percent.setText(f"{pct}%")
        self._bar.setValue(pct)

    def set_unmetered(self, detail: str = "Not on plan") -> None:
        self._amount.setText(detail)
        self._percent.setText("—")
        self._bar.setValue(0)
