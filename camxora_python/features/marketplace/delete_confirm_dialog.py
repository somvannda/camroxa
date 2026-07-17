"""Delete confirmation dialog for marketplace-installed templates.

Warns the user that deleting a marketplace template will require reinstalling
it from the marketplace catalog.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MarketplaceDeleteConfirmDialog(QDialog):
    """Confirmation dialog shown before deleting a marketplace-installed template.

    Displays a warning that the template was installed from the marketplace and
    will need to be reinstalled if deleted.

    Usage:
        dialog = MarketplaceDeleteConfirmDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # User confirmed deletion
            ...
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Delete Marketplace Template")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Warning message
        message = QLabel(
            "This template was installed from the marketplace. "
            "Deleting it will require reinstalling from the marketplace catalog. "
            "Are you sure?"
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(message)

        # Action buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("destructive_button")
        delete_btn.setStyleSheet(
            "QPushButton#destructive_button {"
            " background-color: #dc2626;"
            " color: #ffffff;"
            " border: none;"
            " border-radius: 4px;"
            " padding: 6px 16px;"
            " font-weight: bold;"
            "}"
            "QPushButton#destructive_button:hover {"
            " background-color: #b91c1c;"
            "}"
        )
        delete_btn.clicked.connect(self.accept)
        button_row.addWidget(delete_btn)

        layout.addLayout(button_row)

    def confirmed(self) -> bool:
        """Execute the dialog and return True if the user confirmed deletion.

        Convenience method that wraps exec() and checks the result code.

        Returns:
            True if the user clicked "Delete", False if they cancelled.
        """
        return self.exec() == QDialog.DialogCode.Accepted
