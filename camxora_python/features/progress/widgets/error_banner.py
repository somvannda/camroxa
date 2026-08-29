"""Progress error and warning banners — compact studio panels."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from features.create.widgets.icons import apply_button_icon, icon_label

ERROR_MESSAGE = (
    "Progress data could not be loaded. Check that the API server is running and "
    "the `/progress` endpoint is available."
)


class ProgressErrorBanner(QFrame):
    retry_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("progress_error_banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(icon_label("triangle-alert", size=16, color="#FCA5A5"), 0, Qt.AlignmentFlag.AlignTop)
        self._label = QLabel(ERROR_MESSAGE)
        self._label.setWordWrap(True)
        self._label.setObjectName("progress_error_text")
        layout.addWidget(self._label, 1)
        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setObjectName("SecondaryButton")
        self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_btn.setFixedHeight(28)
        apply_button_icon(self._retry_btn, "refresh-cw")
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        layout.addWidget(self._retry_btn, 0, Qt.AlignmentFlag.AlignVCenter)

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


class ProgressWarningBanner(QFrame):
    details_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("progress_warning_banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(icon_label("triangle-alert", size=16, color="#FCD34D"), 0, Qt.AlignmentFlag.AlignTop)
        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setObjectName("progress_warning_text")
        layout.addWidget(self._label, 1)
        self._details_btn = QPushButton("View Details")
        self._details_btn.setObjectName("SecondaryButton")
        self._details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._details_btn.setFixedHeight(28)
        apply_button_icon(self._details_btn, "search")
        self._details_btn.clicked.connect(self.details_requested.emit)
        layout.addWidget(self._details_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hide()

    def set_message(self, message: str) -> None:
        text = str(message or "").strip()
        self._label.setText(text)
        self.setVisible(bool(text))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#92400E"), 1))
        painter.setBrush(QColor("#2A1F10"))
        painter.drawRoundedRect(rect, 6, 6)
        painter.end()
