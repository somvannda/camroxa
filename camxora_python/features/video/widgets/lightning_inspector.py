"""Lightning domain inspector — multi-layer bolts with free position."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from features.video.widgets.inspector_fields import InspectorSection
from features.video.widgets.lightning_layer_editor import LightningLayerEditor


class LightningInspector(QWidget):
    draft_patch_requested = Signal(dict)
    layer_patch_requested = Signal(dict)
    layer_add_requested = Signal()
    layer_duplicate_requested = Signal()
    layer_delete_requested = Signal()
    layer_move_up_requested = Signal()
    layer_move_down_requested = Signal()
    layer_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._enabled_toggle: QCheckBox | None = None
        self._layer_editor = LightningLayerEditor(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Lightning",
            subtitle="Background lightning bolts. Stack many layers; each has its own style and position.",
        )
        self._enabled_toggle = QCheckBox("Enable Lightning")
        self._enabled_toggle.toggled.connect(
            lambda checked: self.draft_patch_requested.emit({"lightningEnabled": checked})
        )
        section.add_widget(self._enabled_toggle)
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
                self._enabled_toggle.setChecked(bool(draft.get("lightningEnabled", True)))
            self._layer_editor.bind_layers(layers, selected_index=selected_layer_index)
        finally:
            self._binding = False
