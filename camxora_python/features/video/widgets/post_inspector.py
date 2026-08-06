"""Post-processing inspector — whole-frame stack (P10)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from features.video.lib.composition_draft import composition_axis_options
from features.video.widgets.inspector_fields import InspectorSection
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


class PostInspector(QWidget):
    draft_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._checks: dict[str, QCheckBox] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Post Processing",
            subtitle="Whole-frame grade / bloom / grain — not Spectrum materials.",
        )
        note = QLabel("Toggle effects in the stack. Order follows catalog order.")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        section.add_widget(note)

        for eid, label in composition_axis_options()["post_effects"]:
            box = QCheckBox(label)
            box.toggled.connect(self._emit)
            self._checks[eid] = box
            section.add_widget(box)

        root.addWidget(section)
        root.addStretch()

    def _emit(self) -> None:
        if self._binding:
            return
        enabled = [eid for eid, box in self._checks.items() if box.isChecked()]
        self.draft_patch_requested.emit({"compositionPostEffects": enabled})

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        selected = draft.get("compositionPostEffects")
        selected_set = set(selected) if isinstance(selected, list) else set()
        for eid, box in self._checks.items():
            box.setChecked(eid in selected_set)
        self._binding = False

    def mount_effect_pack_selector(self, _selector: QWidget) -> None:
        pass
