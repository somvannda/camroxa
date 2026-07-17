"""Dashboard error banner — matches HomePage.tsx rose card."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

ERROR_MESSAGE = (
    "Unable to load dashboard statistics right now. The shell still works, but dashboard data "
    "needs the backend stats endpoint to respond successfully."
)


class DashboardErrorBanner(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboard_error_banner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        label = QLabel(ERROR_MESSAGE)
        label.setWordWrap(True)
        label.setObjectName("dashboard_error_text")
        layout.addWidget(label)
