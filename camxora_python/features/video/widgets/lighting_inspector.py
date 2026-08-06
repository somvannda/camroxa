"""Lighting inspector — effect × trigger (P7)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from features.video.lib.composition_draft import composition_axis_options
from features.video.widgets.composition_axis_combo import populate_axis_combo, set_combo_data
from features.video.widgets.inspector_fields import InspectorSection
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row


class LightingInspector(QWidget):
    draft_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Lighting",
            subtitle="Layer 2 bolts / aura / beams — not whole-frame post or atmosphere.",
        )
        note = QLabel("Trigger uses audio buses (Vocals / Melody / Snare are FFT heuristics).")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        section.add_widget(note)

        axes = composition_axis_options()
        self._effect = QComboBox()
        populate_axis_combo(self._effect, axes["lighting_effects"])
        self._effect.currentIndexChanged.connect(self._emit)
        section.add_widget(form_row("Effect", self._effect))

        self._trigger = QComboBox()
        populate_axis_combo(self._trigger, axes["lighting_triggers"], include_none=False)
        self._trigger.currentIndexChanged.connect(self._emit)
        section.add_widget(form_row("Trigger", self._trigger))

        root.addWidget(section)
        root.addStretch()

    def _emit(self) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(
            {
                "compositionLightingEffect": self._effect.currentData() or "none",
                "compositionLightingTrigger": self._trigger.currentData() or "none",
            }
        )

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        set_combo_data(self._effect, str(draft.get("compositionLightingEffect") or "none"))
        set_combo_data(self._trigger, str(draft.get("compositionLightingTrigger") or "none"))
        self._binding = False

    def mount_effect_pack_selector(self, _selector: QWidget) -> None:
        pass
