"""Lightning domain inspector — multi-layer bolts with free position."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from features.create.widgets.studio_controls import StudioCheckBox

from features.video.lib.lightning_style_registry import LIGHTNING_PRESET_OPTIONS
from features.video.widgets.inspector_fields import InspectorSection
from features.video.widgets.lightning_layer_editor import LightningLayerEditor
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import note_box


class LightningInspector(QWidget):
    draft_patch_requested = Signal(dict)
    layer_patch_requested = Signal(dict)
    layer_add_requested = Signal()
    layer_duplicate_requested = Signal()
    layer_delete_requested = Signal()
    layer_move_up_requested = Signal()
    layer_move_down_requested = Signal()
    layer_selected = Signal(int)
    preset_apply_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._enabled_toggle: StudioCheckBox | None = None
        self._layer_editor = LightningLayerEditor(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Lightning",
            subtitle="Background lightning bolts. Stack many layers; each has its own style and position.",
        )
        self._enabled_toggle = StudioCheckBox("Enable Lightning")
        self._enabled_toggle.toggled.connect(
            lambda checked: self.draft_patch_requested.emit({"lightningEnabled": checked})
        )
        section.add_widget(self._enabled_toggle)

        preset_label = QLabel("Bolt Preset")
        preset_label.setObjectName(SUBTITLE_LABEL_ID)
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(8)
        preset_row.addWidget(preset_label)
        self._preset_combo = QComboBox()
        for value, label in LIGHTNING_PRESET_OPTIONS:
            self._preset_combo.addItem(label, value)
        apply_btn = QPushButton("Apply Preset")
        apply_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        apply_btn.setToolTip("Apply the selected look to the current bolt layer.")
        apply_btn.clicked.connect(self._emit_preset_apply)
        preset_row.addWidget(self._preset_combo, stretch=1)
        preset_row.addWidget(apply_btn)
        preset_host = QWidget()
        preset_host.setLayout(preset_row)
        section.add_widget(preset_host)
        section.add_widget(
            note_box(
                "Presets restyle the selected bolt (style, trigger, glow, color). "
                "Add layers for more strikes. Phase C also locks seed for stable shapes."
            )
        )
        root.addWidget(section)

        self._layer_editor.layer_patch_requested.connect(self.layer_patch_requested.emit)
        self._layer_editor.layer_add_requested.connect(self.layer_add_requested.emit)
        self._layer_editor.layer_duplicate_requested.connect(self.layer_duplicate_requested.emit)
        self._layer_editor.layer_delete_requested.connect(self.layer_delete_requested.emit)
        self._layer_editor.layer_move_up_requested.connect(self.layer_move_up_requested.emit)
        self._layer_editor.layer_move_down_requested.connect(self.layer_move_down_requested.emit)
        self._layer_editor.layer_selected.connect(self.layer_selected.emit)
        root.addWidget(self._layer_editor)
        root.addStretch()

    def _emit_preset_apply(self) -> None:
        value = self._preset_combo.currentData()
        if isinstance(value, str) and value:
            self.preset_apply_requested.emit(value)

    def mount_effect_pack_selector(self, selector: QWidget) -> None:
        # Packs can come later; keep API parity with other domain inspectors.
        selector.setParent(self)
        selector.hide()

    def bind_draft(
        self,
        draft: dict,
        *,
        layers: list[dict],
        selected_layer_index: int,
    ) -> None:
        self._binding = True
        try:
            if self._enabled_toggle is not None:
                self._enabled_toggle.setChecked(bool(draft.get("lightningEnabled", False)))
            self._layer_editor.bind_layers(layers, selected_index=selected_layer_index)
        finally:
            self._binding = False
