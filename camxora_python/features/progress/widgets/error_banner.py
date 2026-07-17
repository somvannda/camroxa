"""Progress error banner — standard dashboard_error_banner styling."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

ERROR_MESSAGE = (
    "Progress data could not be loaded. Check that the API server is running and "
    "the `/progress` endpoint is available."
)


class ProgressErrorBanner(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboard_error_banner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self._label = QLabel(ERROR_MESSAGE)
        self._label.setWordWrap(True)
        self._label.setObjectName("dashboard_error_text")
        layout.addWidget(self._label)

    def set_message(self, message: str) -> None:
        self._label.setText(message)
