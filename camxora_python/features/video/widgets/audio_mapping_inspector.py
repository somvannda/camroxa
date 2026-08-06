"""Audio Mapping matrix — bus → scene target (P11)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from features.video.lib.composition_draft import composition_axis_options
from features.video.widgets.composition_axis_combo import populate_axis_combo, set_combo_data
from features.video.widgets.inspector_fields import InspectorSection
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row


class AudioMappingInspector(QWidget):
    draft_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._combos: dict[str, QComboBox] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Audio Mapping",
            subtitle="Route audio buses to Lighting / Particles / Camera / Logo.",
        )
        note = QLabel(
            "Vocals, Melody, and Snare are v1 FFT heuristics (smoothed band proxies), "
            "not stem separation."
        )
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        section.add_widget(note)

        axes = composition_axis_options()
        buses = axes["audio_buses"]
        for target, label in axes["audio_targets"]:
            combo = QComboBox()
            populate_axis_combo(combo, buses, include_none=True, none_label="None")
            combo.currentIndexChanged.connect(self._emit)
            self._combos[target] = combo
            section.add_widget(form_row(label, combo))
        root.addWidget(section)
        root.addStretch()

    def _emit(self) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(
            {
                "compositionAudioMapping": {
                    target: combo.currentData() or "none"
                    for target, combo in self._combos.items()
                }
            }
        )

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        mapping = draft.get("compositionAudioMapping")
        mapping = mapping if isinstance(mapping, dict) else {}
        for target, combo in self._combos.items():
            set_combo_data(combo, str(mapping.get(target) or "none"))
        self._binding = False

    def mount_effect_pack_selector(self, _selector: QWidget) -> None:
        pass
