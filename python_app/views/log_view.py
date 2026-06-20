"""Log page — displays real-time application logs in the UI."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .helpers.style_helper import set_panel_role, set_field_role


class LogViewMixin:
    """Mixin providing the Log page builder for MainWindow."""

    def _build_log_workspace_page(self) -> QWidget:
        page = QWidget()
        set_panel_role(page, "center")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel("Application Log")
        self._set_label_role(title, "sectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self.log_clear_button = QPushButton("Clear")
        self._set_button_role(self.log_clear_button, "secondary")
        self.log_clear_button.clicked.connect(self._on_log_clear_clicked)
        header_layout.addWidget(self.log_clear_button)

        self.log_scroll_button = QPushButton("Scroll to Bottom")
        self._set_button_role(self.log_scroll_button, "secondary")
        self.log_scroll_button.clicked.connect(self._on_log_scroll_to_bottom)
        header_layout.addWidget(self.log_scroll_button)

        layout.addWidget(header)

        self.log_text_widget = QPlainTextEdit()
        self.log_text_widget.setReadOnly(True)
        self.log_text_widget.setMaximumBlockCount(5000)  # Keep last 5000 lines
        self.log_text_widget.setFont(QFont("Consolas", 9))
        set_field_role(self.log_text_widget, "logConsole")
        self.log_text_widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.log_text_widget, 1)

        self.log_status_label = QLabel("Logging active")
        self._set_label_role(self.log_status_label, "statusMuted")
        layout.addWidget(self.log_status_label)

        return page

    def _on_log_clear_clicked(self):
        if hasattr(self, "log_text_widget"):
            self.log_text_widget.clear()

    def _on_log_scroll_to_bottom(self):
        if hasattr(self, "log_text_widget"):
            sb = self.log_text_widget.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _append_log_line(self, text: str):
        """Append a log line to the log widget. Thread-safe via signal."""
        if hasattr(self, "log_text_widget"):
            self.log_text_widget.appendPlainText(str(text or "").rstrip())
            # Auto-scroll if near bottom
            sb = self.log_text_widget.verticalScrollBar()
            if sb.value() >= sb.maximum() - 50:
                sb.setValue(sb.maximum())
