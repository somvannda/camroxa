"""Membership metric bar — Create-page slider colors on a compact meter."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from features.create.create_styles import STUDIO_PURPLE_BRIGHT, STUDIO_TEXT_MUTED
from shared.lib.ui_font import studio_font

BAR_COLORS = {
    "emerald": STUDIO_PURPLE_BRIGHT,
    "sky": STUDIO_TEXT_MUTED,
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
        self.setObjectName("TransparentBlock")
        self._bar_hex = BAR_COLORS.get(bar_color, BAR_COLORS["emerald"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label)
        self._label.setObjectName("FieldLabel")
        self._label.setFont(studio_font(12, uppercase=True))
        header.addWidget(self._label)
        header.addStretch()
        self._value = QLabel("--")
        self._value.setObjectName("PlanMeta")
        self._value.setFont(studio_font(12))
        header.addWidget(self._value)
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

    def set_metric(self, value_text: str, percent: int) -> None:
        self._value.setText(value_text)
        self._bar.setValue(max(0, min(100, percent)))
