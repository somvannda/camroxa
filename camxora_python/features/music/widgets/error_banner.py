"""Music workspace error banner — compact studio danger panel."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from features.create.widgets.icons import icon_label

LOAD_ERROR = "Unable to load the music workspace from the current backend contracts."


class MusicErrorBanner(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("music_error_banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(icon_label("triangle-alert", size=16, color="#FCA5A5"), 0, Qt.AlignmentFlag.AlignTop)
        self._label = QLabel(LOAD_ERROR)
        self._label.setWordWrap(True)
        self._label.setObjectName("music_error_text")
        layout.addWidget(self._label, 1)

    def set_message(self, message: str) -> None:
        self._label.setText(message)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#7F1D1D"), 1))
        painter.setBrush(QColor("#2A1220"))
        painter.drawRoundedRect(rect, 6, 6)
        painter.end()
