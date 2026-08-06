"""Color palette inspector — global composition axis."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from features.video.lib.composition_draft import composition_axis_options
from features.video.widgets.composition_axis_combo import populate_axis_combo, set_combo_data
from features.video.widgets.inspector_fields import InspectorSection
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row


class PaletteInspector(QWidget):
    draft_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Color Palette",
            subtitle="Global palette drives spectrum / particles / lighting tints.",
        )
        note = QLabel("Orthogonal to shape, material, and animation.")
        note.setObjectName(SUBTITLE_LABEL_ID)
        note.setWordWrap(True)
        section.add_widget(note)

        self._palette = QComboBox()
        populate_axis_combo(
            self._palette,
            composition_axis_options()["palettes"],
            include_none=True,
            none_label="None (default colors)",
        )
        self._palette.currentIndexChanged.connect(self._emit)
        section.add_widget(form_row("Palette", self._palette))
        root.addWidget(section)
        root.addStretch()

    def _emit(self) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(
            {"compositionColorPalette": self._palette.currentData() or "none"}
        )

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        set_combo_data(self._palette, str(draft.get("compositionColorPalette") or "none"))
        self._binding = False

    def mount_effect_pack_selector(self, _selector: QWidget) -> None:
        """Legacy packs are not scene authority — no-op."""
