"""Compact KPI panel using Create studio chrome."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from features.create.widgets.icons import create_icon
from features.create.widgets.studio_panel import StudioPanel
from shared.lib.ui_font import studio_font


class KpiCard(StudioPanel):
    def __init__(
        self,
        title: str,
        *,
        symbol: str,
        accent: str = "violet",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumHeight(86)
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("FieldLabel")
        title_label.setFont(studio_font(11))
        text.addWidget(title_label)
        self._value = QLabel("--")
        self._value.setObjectName("KpiValue")
        self._value.setFont(studio_font(20))
        text.addWidget(self._value)
        self._delta = QLabel("—")
        self._delta.setObjectName("KpiDeltaFlat")
        self._delta.setFont(studio_font(11))
        text.addWidget(self._delta)
        root.addLayout(text, 1)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        icon.setPixmap(create_icon(symbol, size=16, color="#8FA4BB").pixmap(16, 16))
        root.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_delta(self, text: str, *, tone: str = "flat") -> None:
        self._delta.setText(text or "—")
        role = {"up": "KpiDeltaUp", "down": "KpiDeltaDown"}.get(tone, "KpiDeltaFlat")
        self._delta.setObjectName(role)
        self._delta.style().unpolish(self._delta)
        self._delta.style().polish(self._delta)
