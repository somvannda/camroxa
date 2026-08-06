"""Text composition inspector — typography enable axis (Album/Title stay on right rail)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from features.video.widgets.inspector_fields import InspectorSection
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


class TextCompositionInspector(QWidget):
    draft_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Text",
            subtitle="Typography domains — Album / Title style details stay on the right rail.",
        )
        note = QLabel(
            "Text is Layer 1 typography. Overlay is a separate scene object for frames/stickers."
        )
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        section.add_widget(note)

        self._enabled = QCheckBox("Text overlays enabled")
        self._enabled.toggled.connect(self._emit)
        section.add_widget(self._enabled)

        root.addWidget(section)
        root.addStretch()

    def _emit(self) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(
            {"compositionTextEnabled": self._enabled.isChecked()}
        )

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(draft.get("compositionTextEnabled")))
        self._binding = False

    def mount_effect_pack_selector(self, _selector: QWidget) -> None:
        pass
