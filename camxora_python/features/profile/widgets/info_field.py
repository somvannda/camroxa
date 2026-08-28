"""Compact read-only label/value field used by Profile cards."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from features.create.create_styles import STUDIO_PURPLE_BRIGHT
from features.profile.widgets.icons import icon_tile


class InfoField(QWidget):
    def __init__(
        self,
        label: str,
        value: str = "--",
        *,
        icon: QIcon | None = None,
        icon_name: str | None = None,
        icon_color: str = STUDIO_PURPLE_BRIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InfoField")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        if icon_name:
            glyph = QLabel()
            glyph.setFixedSize(28, 28)
            glyph.setPixmap(icon_tile(icon_name, color=icon_color, tile=28, icon=14))
            row.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignTop)
        elif icon is not None:
            glyph = QLabel()
            glyph.setPixmap(icon.pixmap(14, 14))
            glyph.setFixedSize(16, 16)
            glyph.setAlignment(Qt.AlignmentFlag.AlignTop)
            row.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        title = QLabel(label.upper())
        title.setObjectName("InfoLabel")
        copy.addWidget(title)
        self._value = QLabel(value)
        self._value.setObjectName("InfoValue")
        self._value.setWordWrap(True)
        copy.addWidget(self._value)
        row.addLayout(copy, 1)

    def set_value(self, value: str, *, success: bool = False) -> None:
        self._value.setText(value)
        self._value.setObjectName("InfoValueSuccess" if success else "InfoValue")
        self._value.style().unpolish(self._value)
        self._value.style().polish(self._value)
