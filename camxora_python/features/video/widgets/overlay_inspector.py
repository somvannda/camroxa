"""Overlay inspector — top composites (frames / stickers / watermarks)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QVBoxLayout, QWidget

from features.video.lib.composition_draft import composition_axis_options
from features.video.widgets.composition_axis_combo import populate_axis_combo, set_combo_data
from features.video.widgets.inspector_fields import InspectorSection
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row


class OverlayInspector(QWidget):
    draft_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Overlay",
            subtitle="Top-of-frame composites — different from Text typography.",
        )
        note = QLabel("Enable overlays and choose a shared animation behavior.")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        section.add_widget(note)

        self._enabled = QCheckBox("Overlay enabled")
        self._enabled.toggled.connect(self._emit)
        section.add_widget(self._enabled)

        self._animation = QComboBox()
        populate_axis_combo(self._animation, composition_axis_options()["animations"])
        self._animation.currentIndexChanged.connect(self._emit)
        section.add_widget(form_row("Animation", self._animation))

        root.addWidget(section)
        root.addStretch()

    def _emit(self) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(
            {
                "compositionOverlayEnabled": self._enabled.isChecked(),
                "compositionOverlayAnimation": self._animation.currentData() or "none",
            }
        )

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        self._enabled.setChecked(bool(draft.get("compositionOverlayEnabled")))
        set_combo_data(
            self._animation, str(draft.get("compositionOverlayAnimation") or "none")
        )
        self._binding = False

    def mount_effect_pack_selector(self, _selector: QWidget) -> None:
        pass
