"""Image preview card with optional source-mode control."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID

_SOURCE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Category", "category"),
    ("User reference", "personal_reference"),
    ("Prompt only", "prompt_only"),
)


class PreviewCard(QFrame):
    source_mode_changed = Signal(str)

    def __init__(
        self,
        title: str,
        placeholder: str,
        *,
        source_label: str = "Source",
        parent: QWidget | None = None,
    ) -> None:
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

        source_heading = QLabel(source_label.upper())
        source_heading.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(source_heading)

        self._source_mode = QComboBox()
        for label, value in _SOURCE_OPTIONS:
            self._source_mode.addItem(label, value)
        self._source_mode.currentIndexChanged.connect(self._emit_source_mode)
        root.addWidget(self._source_mode)

        helper = QLabel(
            "Saved to Preferences. Prompt only uses the prompt box on the left. "
            "User reference is coming soon."
        )
        helper.setObjectName(SUBTITLE_LABEL_ID)
        helper.setWordWrap(True)
        root.addWidget(helper)

        self._preview = QLabel()
        self._preview.setMinimumHeight(220)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setObjectName("music_section")
        self._preview.setText(placeholder)
        self._placeholder = placeholder
        root.addWidget(self._preview)

    def source_mode(self) -> str:
        return str(self._source_mode.currentData() or "category")

    def set_source_mode(self, mode: str) -> None:
        normalized = str(mode or "category").strip().lower()
        if normalized in {"prompt", "prompt_only"}:
            normalized = "prompt_only"
        elif normalized in {"personal", "personal_reference", "user_reference"}:
            normalized = "personal_reference"
        else:
            normalized = "category"
        index = self._source_mode.findData(normalized)
        if index < 0:
            return
        self._source_mode.blockSignals(True)
        self._source_mode.setCurrentIndex(index)
        self._source_mode.blockSignals(False)

    def _emit_source_mode(self, *_args: object) -> None:
        self.source_mode_changed.emit(self.source_mode())

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
