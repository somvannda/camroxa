"""Camera inspector — scene-level behaviors (P8)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from features.video.lib.composition_draft import composition_axis_options
from features.video.widgets.composition_axis_combo import populate_axis_combo, set_combo_data
from features.video.widgets.inspector_fields import InspectorSection
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row


class CameraInspector(QWidget):
    draft_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Camera",
            subtitle="Scene-level camera — not a Spectrum setting.",
        )
        note = QLabel("Audio Mapping can drive camera shake / punch from a bus.")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        section.add_widget(note)

        self._behavior = QComboBox()
        populate_axis_combo(self._behavior, composition_axis_options()["camera_behaviors"])
        self._behavior.currentIndexChanged.connect(self._emit)
        section.add_widget(form_row("Behavior", self._behavior))

        root.addWidget(section)
        root.addStretch()

    def _emit(self) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(
            {"compositionCameraBehavior": self._behavior.currentData() or "none"}
        )

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        set_combo_data(self._behavior, str(draft.get("compositionCameraBehavior") or "none"))
        self._binding = False

    def mount_effect_pack_selector(self, _selector: QWidget) -> None:
        pass
