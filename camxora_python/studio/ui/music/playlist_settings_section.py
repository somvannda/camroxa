"""Card-style section container for the Playlist Settings tab."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from studio.ui.inspector_layout import FIELD_GAP


class PlaylistSettingsSection(QFrame):
    """Grouped settings block with title and inset card styling."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlaylistSettingsSection")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(FIELD_GAP)

        heading = QLabel(title)
        heading.setObjectName("DetailsSectionTitle")
        root.addWidget(heading)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(FIELD_GAP)
        root.addLayout(self.body)
