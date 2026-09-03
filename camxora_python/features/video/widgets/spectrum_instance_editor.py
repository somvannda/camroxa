"""Spectrum instance stack — multiple independent Spectrums (outer combo)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QWidget,
)

from features.create.widgets.studio_controls import StudioCheckBox

from features.video.widgets.inspector_fields import InspectorSection, action_icon_button
from shared.widgets.settings_ui import form_row, note_box


class SpectrumInstanceEditor(InspectorSection):
    """Add / select independent Spectrum instances (each has its own rings + position)."""

    instance_selected = Signal(int)
    instance_add_requested = Signal()
    instance_duplicate_requested = Signal()
    instance_delete_requested = Signal()
    instance_move_up_requested = Signal()
    instance_move_down_requested = Signal()
    instance_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Spectrums",
            subtitle="Add multiple Spectrums — each has its own position, attach, audio, and ring layers.",
            parent=parent,
        )
        self._binding = False
        self._instances: list[dict] = []
        self._selected_index = 0

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        actions.addWidget(self._combo, stretch=1)
        for icon, tip, slot in (
            ("plus", "Add spectrum instance", self.instance_add_requested.emit),
            ("copy", "Duplicate selected spectrum", self.instance_duplicate_requested.emit),
            ("trash-2", "Delete selected spectrum", self.instance_delete_requested.emit),
            ("chevron-up", "Move selected spectrum up", self.instance_move_up_requested.emit),
            ("chevron-down", "Move selected spectrum down", self.instance_move_down_requested.emit),
        ):
            btn = action_icon_button(icon, tooltip=tip, on_click=slot)
            actions.addWidget(btn)
            if icon == "trash-2":
                self._delete_btn = btn
            elif icon == "chevron-up":
                self._up_btn = btn
            elif icon == "chevron-down":
                self._down_btn = btn
        host = QWidget()
        host.setLayout(actions)
        self.add_widget(host)

        self._name_input = QLineEdit()
        self._name_input.textChanged.connect(lambda text: self._emit_patch({"name": text}))
        self.add_widget(form_row("Name", self._name_input))

        self._enabled = StudioCheckBox("Enabled")
        self._enabled.toggled.connect(lambda checked: self._emit_patch({"enabled": checked}))
        self.add_widget(self._enabled)

        self.add_widget(
            note_box(
                "Each Spectrum is independent: drag on the preview to place the selected one. "
                "Ring layers below belong only to the selected Spectrum. "
                "Max 8 Spectrums."
            )
        )

    def _emit_patch(self, patch: dict) -> None:
        if self._binding:
            return
        self.instance_patch_requested.emit(patch)

    def _on_combo_changed(self, index: int) -> None:
        if self._binding or index < 0:
            return
        self.instance_selected.emit(index)

    def bind_instances(self, instances: list[dict], *, selected_index: int) -> None:
        self._binding = True
        try:
            self._instances = list(instances or [])
            self._selected_index = max(0, min(selected_index, max(len(self._instances) - 1, 0)))
            self._combo.blockSignals(True)
            self._combo.clear()
            for index, item in enumerate(self._instances):
                name = str(item.get("name") or "").strip() or f"Spectrum {index + 1}"
                enabled = "✓" if bool(item.get("enabled", True)) else "·"
                self._combo.addItem(f"{enabled} {name}", index)
            if self._instances:
                self._combo.setCurrentIndex(self._selected_index)
            self._combo.blockSignals(False)

            self._delete_btn.setEnabled(len(self._instances) >= 2)
            self._up_btn.setEnabled(len(self._instances) >= 2 and self._selected_index > 0)
            self._down_btn.setEnabled(
                len(self._instances) >= 2 and self._selected_index < len(self._instances) - 1
            )
            if not self._instances:
                return
            inst = self._instances[self._selected_index]
            self._name_input.blockSignals(True)
            self._name_input.setText(str(inst.get("name") or ""))
            self._name_input.blockSignals(False)
            self._enabled.setChecked(bool(inst.get("enabled", True)))
        finally:
            self._binding = False
