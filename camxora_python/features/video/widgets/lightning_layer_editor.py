"""Lightning layer stack editor."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDial,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.lightning_style_registry import (
    LIGHTNING_BLEND_OPTIONS,
    LIGHTNING_DIRECTION_OPTIONS,
    LIGHTNING_SPAWN_OPTIONS,
    LIGHTNING_STYLE_OPTIONS,
    LIGHTNING_TRIGGER_OPTIONS,
    MAX_LIGHTNING_LAYERS,
    normalize_lightning_blend,
    normalize_lightning_direction,
    normalize_lightning_spawn,
    normalize_lightning_style,
    normalize_lightning_trigger,
)
from features.create.widgets.studio_controls import StudioCheckBox
from features.video.widgets.inspector_fields import InspectorSection, build_color_field, build_float_slider
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
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
            subtitle=(
                f"Add up to {MAX_LIGHTNING_LAYERS} bolts — each layer is one lightning. "
                "Style and position are per bolt."
            ),
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
            if label == "Add":
                self._add_btn = btn
            elif label == "Dup":
                self._dup_btn = btn
            elif label == "Del":
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

        self._enabled = StudioCheckBox("Enabled")
        self._enabled.toggled.connect(lambda checked: self.layer_patch_requested.emit({"enabled": checked}))
        self.add_widget(self._enabled)

        self.add_widget(self._build_combo("style", "Style", LIGHTNING_STYLE_OPTIONS))
        self.add_widget(self._build_combo("spawnMode", "Spawn", LIGHTNING_SPAWN_OPTIONS))
        self.add_widget(self._build_combo("direction", "Direction", LIGHTNING_DIRECTION_OPTIONS))
        self.add_widget(self._build_combo("blend", "Blend", LIGHTNING_BLEND_OPTIONS))
        self.add_widget(self._build_combo("trigger", "Trigger", LIGHTNING_TRIGGER_OPTIONS))

        self._seed_lock = StudioCheckBox("Lock Seed (stable bolt shape)")
        self._seed_lock.toggled.connect(lambda checked: self.layer_patch_requested.emit({"seedLock": checked}))
        self.add_widget(self._seed_lock)

        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_btn = QPushButton("Reset Position (center)")
        reset_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        reset_btn.clicked.connect(lambda: self.layer_patch_requested.emit({"x": 0.0, "y": 0.0}))
        reset_row.addWidget(reset_btn)
        reset_row.addStretch(1)
        reset_host = QWidget()
        reset_host.setLayout(reset_row)
        self.add_widget(reset_host)

        self.add_widget(
            note_box(
                "Drag the selected bolt on the preview to place it (Anchored spawn). "
                "Random on screen = new full-frame position every strike. "
                "Rotation wheel spins the bolt 0–360° on top of Direction. "
                "Branchiness = side twigs on this one bolt (0 = clean stroke, 1 = up to 2 forks). "
                f"Use Add for more independent bolts (max {MAX_LIGHTNING_LAYERS}). "
                "Strike Motion Speed / React Motion Speed control timing feel — not bolt length. "
                "Length React (optional) is the only control that lets volume stretch reach. "
                "Thickness Taper: thin at the start → thicker toward the tip. "
                "Glow adds the bright air bloom around each strike. "
                "Opacity 0 fully hides the bolt (including glow)."
            )
        )

        self.add_widget(self._build_rotation_wheel())

        for field, label, minimum, maximum, step in (
            ("length", "Bolt Length", 20, 600, 5),
            ("thickness", "Thickness", 0, 24, 0.25),
            ("taper", "Thickness Taper", 0, 1, 0.05),
            ("glow", "Glow", 0, 1, 0.05),
            ("branchiness", "Branchiness", 0, 1, 0.05),
            ("opacity", "Opacity", 0, 1, 0.05),
            ("intensity", "Intensity", 0, 1, 0.05),
            ("reactivity", "Audio Reactivity", 0, 1, 0.05),
            ("reactMotionSpeed", "React Motion Speed", 0, 4, 0.05),
            ("speed", "Strike Motion Speed", 0, 4, 0.05),
            ("flashRate", "Flash Rate", 0, 4, 0.05),
            ("lengthReactivity", "Length React (volume→reach)", 0, 1, 0.05),
            ("triggerThreshold", "Trigger Threshold", 0, 0.95, 0.01),
            ("seed", "Seed", 0, 9999, 1),
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

    def _build_rotation_wheel(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._rotation_label = QLabel("Rotation (0°)")
        self._rotation_label.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._rotation_label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self._rotation_dial = QDial()
        self._rotation_dial.setRange(0, 360)
        self._rotation_dial.setWrapping(True)
        self._rotation_dial.setNotchesVisible(True)
        self._rotation_dial.setFixedSize(96, 96)
        self._rotation_dial.setToolTip("Drag the wheel to rotate the bolt")
        self._rotation_dial.setStyleSheet(
            """
            QDial {
                background-color: #0c1230;
                border: 1px solid #2a3566;
                border-radius: 48px;
            }
            QDial::handle {
                background-color: #a855f7;
            }
            """
        )
        self._rotation_dial.valueChanged.connect(self._on_rotation_dial)

        tip = QLabel("0° = Direction\n90° = clockwise")
        tip.setObjectName(SUBTITLE_LABEL_ID)
        tip_font = QFont("Open Sans")
        tip_font.setPixelSize(12)
        tip.setFont(tip_font)
        tip.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(self._rotation_dial, 0, Qt.AlignmentFlag.AlignLeft)
        row.addWidget(tip, 1)
        layout.addLayout(row)

        # Keep a float setter so bind_layers can drive the dial.
        def _set_rotation(value: float) -> None:
            deg = int(round(max(0.0, min(360.0, float(value))))) % 361
            if deg == 360:
                deg = 0
            self._rotation_dial.blockSignals(True)
            self._rotation_dial.setValue(deg)
            self._rotation_dial.blockSignals(False)
            self._rotation_label.setText(f"Rotation ({deg}°)")

        self._float_setters["rotation"] = _set_rotation
        return host

    def _on_rotation_dial(self, value: int) -> None:
        if self._binding:
            return
        deg = int(value) % 360
        self._rotation_label.setText(f"Rotation ({deg}°)")
        self.layer_patch_requested.emit({"rotation": float(deg)})

    def _build_combo(self, field: str, label: str, options: tuple[tuple[str, str], ...]) -> QWidget:
        combo = QComboBox()
        for value, option_label in options:
            combo.addItem(option_label, value)
        combo.currentIndexChanged.connect(lambda _i, key=field: self._on_combo_changed(key))
        self._combo_fields[field] = combo
        return form_row(label, combo)

    def _add_float(
        self,
        field: str,
        label: str,
        minimum: float,
        maximum: float,
        step: float,
        format_value: Callable[[float], str] | None = None,
    ) -> QWidget:
        widget, setter = build_float_slider(
            label,
            minimum=minimum,
            maximum=maximum,
            step=step,
            value=minimum,
            on_change=lambda value, key=field: self.layer_patch_requested.emit({key: float(value)}),
            format_value=format_value,
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
        elif field == "trigger":
            value = normalize_lightning_trigger(value)
        elif field == "spawnMode":
            value = normalize_lightning_spawn(value)
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

            can_add = len(layers) < MAX_LIGHTNING_LAYERS
            self._add_btn.setEnabled(can_add)
            self._dup_btn.setEnabled(can_add)
            self._delete_btn.setEnabled(len(layers) >= 2)
            self._up_btn.setEnabled(len(layers) >= 2 and self._selected_index > 0)
            self._down_btn.setEnabled(len(layers) >= 2 and self._selected_index < len(layers) - 1)
            if not layer:
                return

            self._name_input.blockSignals(True)
            self._name_input.setText(str(layer.get("name") or ""))
            self._name_input.blockSignals(False)
            self._enabled.setChecked(bool(layer.get("enabled", True)))
            self._seed_lock.setChecked(bool(layer.get("seedLock", False)))

            for field, combo in self._combo_fields.items():
                value = str(layer.get(field) or "")
                if field == "style":
                    value = normalize_lightning_style(value)
                elif field == "direction":
                    value = normalize_lightning_direction(value)
                elif field == "blend":
                    value = normalize_lightning_blend(value)
                elif field == "trigger":
                    value = normalize_lightning_trigger(value)
                elif field == "spawnMode":
                    value = normalize_lightning_spawn(value)
                index = combo.findData(value)
                if index >= 0:
                    combo.setCurrentIndex(index)

            for field, setter in self._float_setters.items():
                raw = layer.get(field, 0.0)
                if raw is None:
                    raw = 0.0
                setter(float(raw))

            color = layer.get("color") if isinstance(layer.get("color"), dict) else {}
            solid = str(color.get("solidColor") or "#e0f2fe")
            if "solidColor" in self._color_setters:
                self._color_setters["solidColor"](solid)
        finally:
            self._binding = False
