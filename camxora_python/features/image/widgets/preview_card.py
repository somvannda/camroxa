"""Image preview card."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID


class PreviewCard(QFrame):
    def __init__(self, title: str, placeholder: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        heading = QLabel(title)
        heading.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(heading)

        subtitle = QLabel("Pinned from the selected queue row.")
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(subtitle)

        self._preview = QLabel()
        self._preview.setMinimumHeight(260)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setObjectName("music_section")
        self._preview.setText(placeholder)
        self._placeholder = placeholder
        root.addWidget(self._preview)

    def set_image_bytes(self, data: bytes | None) -> None:
        if not data:
            self._preview.clear()
            self._preview.setText(self._placeholder)
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._preview.clear()
            self._preview.setText(self._placeholder)
            return
        scaled = pixmap.scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)
        self._preview.setText("")

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        pixmap = self._preview.pixmap()
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                self._preview.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setPixmap(scaled)
