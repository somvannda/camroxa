"""Lightning layer stack editor."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.lightning_style_registry import (
    LIGHTNING_BLEND_OPTIONS,
    LIGHTNING_DIRECTION_OPTIONS,
    LIGHTNING_STYLE_OPTIONS,
    normalize_lightning_blend,
    normalize_lightning_direction,
    normalize_lightning_style,
)
from features.video.widgets.inspector_fields import InspectorSection, build_color_field, build_float_slider
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID
from shared.widgets.settings_ui import form_row, note_box


class LightningLayerEditor(InspectorSection):
    layer_patch_requested = Signal(dict)
    layer_add_requested = Signal()
    layer_duplicate_requested = Signal()
    layer_delete_requested = Signal()
    layer_move_up_requested = Signal()
    layer_move_down_requested = Signal()
    layer_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Lightning Layers",
            subtitle="Add as many bolts as you want. Each layer has its own style and free position.",
            parent=parent,
        )
        self._binding = False
        self._layers: list[dict] = []
        self._selected_index = 0
        self._float_setters: dict[str, Callable[[float], None]] = {}
        self._color_setters: dict[str, Callable[[str], None]] = {}
        self._combo_fields: dict[str, QComboBox] = {}

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        self._layer_combo = QComboBox()
        self._layer_combo.currentIndexChanged.connect(self._on_layer_combo_changed)
        actions.addWidget(self._layer_combo, stretch=1)
        for label, slot in (
            ("Add", self.layer_add_requested.emit),
            ("Dup", self.layer_duplicate_requested.emit),
            ("Del", self.layer_delete_requested.emit),
            ("Up", self.layer_move_up_requested.emit),
            ("Down", self.layer_move_down_requested.emit),
        ):
            btn = QPushButton(label)
            btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
            btn.clicked.connect(slot)
            actions.addWidget(btn)
            if label == "Del":
                self._delete_btn = btn
            elif label == "Up":
                self._up_btn = btn
            elif label == "Down":
                self._down_btn = btn
        host = QWidget()
        host.setLayout(actions)
        self.add_widget(host)

        self._name_input = QLineEdit()
        self._name_input.textChanged.connect(lambda text: self.layer_patch_requested.emit({"name": text}))
        self.add_widget(form_row("Name", self._name_input))

        self._enabled = QCheckBox("Enabled")
        self._enabled.toggled.connect(lambda checked: self.layer_patch_requested.emit({"enabled": checked}))
        self.add_widget(self._enabled)

        self.add_widget(self._build_combo("style", "Style", LIGHTNING_STYLE_OPTIONS))
        self.add_widget(self._build_combo("direction", "Direction", LIGHTNING_DIRECTION_OPTIONS))
        self.add_widget(self._build_combo("blend", "Blend", LIGHTNING_BLEND_OPTIONS))

        self.add_widget(
            note_box(
                "Drag on the preview while the Lightning tab is open to freely position the selected bolt."
            )
        )

        for field, label, minimum, maximum, step in (
            ("x", "Position X", -500, 500, 1),
            ("y", "Position Y", -500, 500, 1),
            ("length", "Bolt Length", 40, 600, 5),
            ("thickness", "Thickness", 0.5, 24, 0.25),
            ("glow", "Glow", 0, 1, 0.05),
            ("branchiness", "Branchiness", 0, 1, 0.05),
            ("opacity", "Opacity", 0, 1, 0.05),
            ("intensity", "Intensity", 0, 1, 0.05),
            ("reactivity", "Audio Reactivity", 0, 1, 0.05),
            ("speed", "Motion Speed", 0.05, 4, 0.05),
            ("flashRate", "Flash Rate", 0.05, 4, 0.05),
        ):
            self.add_widget(self._add_float(field, label, minimum, maximum, step))

        color_widget, color_setter = build_color_field(
            "Bolt Color",
            value="#e0f2fe",
            on_change=lambda value: self.layer_patch_requested.emit(
                {"color": {"mode": "solid", "solidColor": value, "gradientColors": [value, "#38bdf8"]}}
            ),
            parent=self,
        )
        self._color_setters["solidColor"] = color_setter
        self.add_widget(color_widget)

    def _build_combo(self, field: str, label: str, options: tuple[tuple[str, str], ...]) -> QWidget:
        combo = QComboBox()
        for value, option_label in options:
            combo.addItem(option_label, value)
        combo.currentIndexChanged.connect(lambda _i, key=field: self._on_combo_changed(key))
        self._combo_fields[field] = combo
        return form_row(label, combo)

    def _add_float(self, field: str, label: str, minimum: float, maximum: float, step: float) -> QWidget:
        widget, setter = build_float_slider(
            label,
            minimum=minimum,
            maximum=maximum,
            step=step,
            value=minimum,
            on_change=lambda value, key=field: self.layer_patch_requested.emit({key: float(value)}),
        )
        self._float_setters[field] = setter
        return widget

    def _on_combo_changed(self, field: str) -> None:
        if self._binding:
            return
        combo = self._combo_fields.get(field)
        if combo is None:
            return
        value = combo.currentData()
        if not isinstance(value, str):
            return
        if field == "style":
            value = normalize_lightning_style(value)
        elif field == "direction":
            value = normalize_lightning_direction(value)
        elif field == "blend":
            value = normalize_lightning_blend(value)
        self.layer_patch_requested.emit({field: value})

    def _on_layer_combo_changed(self, index: int) -> None:
        if self._binding or index < 0:
            return
        self.layer_selected.emit(index)

    def _selected_layer(self) -> dict | None:
        if not self._layers:
            return None
        index = max(0, min(self._selected_index, len(self._layers) - 1))
        return self._layers[index]

    def bind_layers(self, layers: list[dict], *, selected_index: int) -> None:
        self._binding = True
        try:
            self._layers = layers
            self._selected_index = max(0, min(selected_index, max(len(layers) - 1, 0)))
            layer = self._selected_layer()

            self._layer_combo.blockSignals(True)
            self._layer_combo.clear()
            for index, item in enumerate(layers):
                name = str(item.get("name") or "").strip() or f"Bolt {index + 1}"
                self._layer_combo.addItem(name, index)
            if layers:
                self._layer_combo.setCurrentIndex(self._selected_index)
            self._layer_combo.blockSignals(False)

            self._delete_btn.setEnabled(len(layers) >= 2)
            self._up_btn.setEnabled(len(layers) >= 2 and self._selected_index > 0)
            self._down_btn.setEnabled(len(layers) >= 2 and self._selected_index < len(layers) - 1)
            if not layer:
                return

            self._name_input.blockSignals(True)
            self._name_input.setText(str(layer.get("name") or ""))
            self._name_input.blockSignals(False)
            self._enabled.setChecked(bool(layer.get("enabled", True)))

            for field, combo in self._combo_fields.items():
                value = str(layer.get(field) or "")
                if field == "style":
                    value = normalize_lightning_style(value)
                elif field == "direction":
                    value = normalize_lightning_direction(value)
                elif field == "blend":
                    value = normalize_lightning_blend(value)
                index = combo.findData(value)
                if index >= 0:
                    combo.setCurrentIndex(index)

            for field, setter in self._float_setters.items():
                setter(float(layer.get(field, 0.0) or 0.0))

            color = layer.get("color") if isinstance(layer.get("color"), dict) else {}
            solid = str(color.get("solidColor") or "#e0f2fe")
            if "solidColor" in self._color_setters:
                self._color_setters["solidColor"](solid)
        finally:
            self._binding = False
