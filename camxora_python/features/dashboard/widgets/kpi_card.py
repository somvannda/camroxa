"""KPI card with Material Symbol SVG icon (no background box)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from shared.icons.material_symbols import ACCENT_COLORS, material_symbol_pixmap
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class KpiCard(QFrame):
    def __init__(
        self,
        title: str,
        *,
        symbol: str,
        accent: str = "violet",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName(SUBTITLE_LABEL_ID)
        text_col.addWidget(title_label)
        self._value = QLabel("--")
        self._value.setObjectName(TITLE_LABEL_ID)
        text_col.addWidget(self._value)
        root.addLayout(text_col, stretch=1)

        color = ACCENT_COLORS.get(accent, ACCENT_COLORS["violet"])
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        icon_label.setPixmap(material_symbol_pixmap(symbol, color=color, size=24))
        icon_label.setFixedSize(24, 24)
        root.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

    def set_value(self, value: str) -> None:
        self._value.setText(value)
