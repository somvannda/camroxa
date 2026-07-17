"""Music workspace error banner."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

LOAD_ERROR = "Unable to load the music workspace from the current backend contracts."


class MusicErrorBanner(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboard_error_banner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self._label = QLabel(LOAD_ERROR)
        self._label.setWordWrap(True)
        self._label.setObjectName("dashboard_error_text")
        layout.addWidget(self._label)

    def set_message(self, message: str) -> None:
        self._label.setText(message)
