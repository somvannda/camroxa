"""Workflow error banner — compact studio danger panel."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

ERROR_MESSAGE = "Workflow data could not be loaded from the progress aggregate API."


class WorkflowErrorBanner(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workflow_error_banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        label = QLabel(ERROR_MESSAGE)
        label.setWordWrap(True)
        label.setObjectName("workflow_error_text")
        layout.addWidget(label)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#7F1D1D"), 1))
        painter.setBrush(QColor("#2A1220"))
        painter.drawRoundedRect(rect, 6, 6)
        painter.end()
