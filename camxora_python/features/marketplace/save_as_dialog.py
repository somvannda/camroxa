"""Save As dialog — prompts the user for a new template name when copying a marketplace template.

Provides inline validation (non-empty, non-whitespace, max 100 chars) and returns
the entered name on accept, or None on cancel.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt


class SaveAsDialog(QDialog):
    """Dialog prompting the user for a template name during "Save As".

    Pre-fills the name input with "{original_name} - Copy" and validates
    that the name is non-empty, non-whitespace-only, and at most 100 characters.

    Usage:
        dialog = SaveAsDialog(parent=self, original_name="My Template")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_name()
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        original_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._result_name: str | None = None

        self.setWindowTitle("Save As")
        self.setMinimumWidth(420)
        self.setModal(True)

        default_name = f"{original_name} - Copy" if original_name else "Copy"
        # Truncate default if it exceeds 100 chars
        if len(default_name) > 100:
            default_name = default_name[:100]

        self._build_ui(default_name)

    def _build_ui(self, default_name: str) -> None:
        """Construct the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title_label = QLabel("Save Template As")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "Marketplace templates are read-only. "
            "Enter a name for your editable copy."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc_label)

        # Name input
        input_label = QLabel("Template Name:")
        layout.addWidget(input_label)

        self._name_input = QLineEdit()
        self._name_input.setText(default_name)
        self._name_input.setMaxLength(100)
        self._name_input.setPlaceholderText("Enter template name (max 100 characters)")
        self._name_input.selectAll()
        self._name_input.returnPressed.connect(self._on_save)
        layout.addWidget(self._name_input)

        # Error label (hidden by default)
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #e74c3c; font-size: 11px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Character count
        self._char_count_label = QLabel(f"{len(default_name)}/100")
        self._char_count_label.setStyleSheet("color: #888888; font-size: 11px;")
        self._char_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._char_count_label)

        self._name_input.textChanged.connect(self._on_text_changed)

        # Spacer
        layout.addStretch(1)

        # Action buttons
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addStretch(1)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedHeight(30)
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("Save As")
        self._save_btn.setFixedHeight(30)
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save)
        button_row.addWidget(self._save_btn)

        layout.addLayout(button_row)

    def _on_text_changed(self, text: str) -> None:
        """Update character count and clear error on edit."""
        self._char_count_label.setText(f"{len(text)}/100")
        self._error_label.setVisible(False)

    def _on_save(self) -> None:
        """Validate input and accept if valid."""
        name = self._name_input.text()

        # Validate
        if not name:
            self._show_error("Name cannot be empty.")
            return
        if name.strip() == "":
            self._show_error("Name cannot be whitespace only.")
            return
        if len(name) > 100:
            self._show_error("Name must be at most 100 characters.")
            return

        self._result_name = name
        self.accept()

    def _show_error(self, message: str) -> None:
        """Display inline validation error."""
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._name_input.setFocus()

    def get_name(self) -> str | None:
        """Return the validated name, or None if cancelled.

        Should be called after exec() returns Accepted.
        """
        return self._result_name
