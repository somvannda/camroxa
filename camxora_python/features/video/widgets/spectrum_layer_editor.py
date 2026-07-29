"""Spectrum layer stack editor — port of SpectrumLayerEditor.tsx."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.spectrum_color_engine import (
    SPECTRUM_GRADIENT_PRESET_OPTIONS,
    apply_spectrum_layer_color_patch,
    build_spectrum_gradient_preset_value,
    extract_spectrum_layer_color_model,
    get_spectrum_layer_color_fallback,
    normalize_spectrum_gradient_colors,
)
from features.video.widgets.inspector_fields import InspectorSection, build_color_field, build_float_slider
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row, note_box

GRAVITY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("normal", "Outward (bars raise like a straight EQ)"),
    ("bottom", "Inward (rabbit ears)"),
    ("top", "Top"),
    ("left", "Left"),
    ("right", "Right"),
)

# How the ring is laid out. This is separate from blend mode.
CIRCLE_FORM_OPTIONS: tuple[tuple[str, str], ...] = (
    ("linear", "Linear (straight row)"),
    ("semi", "Circle Raise (180°)"),
    ("full", "Full Circle Raise (360°)"),
)

BLEND_OPTIONS: tuple[tuple[str, str], ...] = (
    ("normal", "Normal (true colors)"),
    ("add", "Additive (brighter / can wash out)"),
    ("screen", "Screen (lighten / can wash out)"),
)

GRADIENT_DIRECTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("left-to-right", "Around Ring"),
    ("top-to-bottom", "Base to Tip"),
    ("radial", "Radial (Base to Tip)"),
    ("circular", "Circular (Around Ring)"),
    ("diagonal", "Diagonal (Around + Tip)"),
)


class SpectrumLayerEditor(InspectorSection):
    draft_patch_requested = Signal(dict)
    layer_patch_requested = Signal(dict)
    layer_color_patch_requested = Signal(dict)
    layer_add_requested = Signal()
    layer_duplicate_requested = Signal()
    layer_delete_requested = Signal()
    layer_move_up_requested = Signal()
    layer_move_down_requested = Signal()
    layer_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Layers",
            subtitle=(
                "Each ring has its own settings. Last in the list draws on top. "
                "Use Up/Down to reorder. Layer Gap changes that ring's size."
            ),
            parent=parent,
        )
        self._binding = False
        self._layers: list[dict] = []
        self._selected_index = 0
        self._color_model: dict[str, Any] = {}
        self._float_setters: dict[str, Callable[[float], None]] = {}
        self._gradient_stop_setters: list[Callable[[str], None]] = []
        self._gradient_stops_host: QWidget | None = None
        self._solid_color_setter: Callable[[str], None] | None = None
        self._gradient_host: QWidget | None = None
        self._solid_host: QWidget | None = None
        self._attach_note: QWidget | None = None

        self._layer_combo = QComboBox()
        self._layer_combo.setToolTip("Selected layer (edits apply only to this ring)")
        self._layer_combo.currentIndexChanged.connect(self._on_layer_combo_changed)
        self.add_widget(self._layer_combo)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.layer_add_requested.emit)
        dup_btn = QPushButton("Duplicate")
        dup_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        dup_btn.clicked.connect(self.layer_duplicate_requested.emit)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._delete_btn.clicked.connect(self.layer_delete_requested.emit)
        self._up_btn = QPushButton("Up")
        self._up_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._up_btn.setToolTip("Move selected layer earlier (draws under)")
        self._up_btn.clicked.connect(self.layer_move_up_requested.emit)
        self._down_btn = QPushButton("Down")
        self._down_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._down_btn.setToolTip("Move selected layer later (draws on top)")
        self._down_btn.clicked.connect(self.layer_move_down_requested.emit)
        for button in (add_btn, dup_btn, self._delete_btn, self._up_btn, self._down_btn):
            actions.addWidget(button)
        action_host = QWidget()
        action_host.setLayout(actions)
        self.add_widget(action_host)

        self._name_input = QLineEdit()
        self._name_input.textChanged.connect(
            lambda text: self.layer_patch_requested.emit({"name": text})
        )
        self.add_widget(form_row("Layer Name", self._name_input))

        self._circle_form_combo = QComboBox()
        self._circle_form_combo.setToolTip(
            "Linear = straight EQ row. Circle Raise = half ring. Full Circle Raise = bars around the whole ring."
        )
        for value, label in CIRCLE_FORM_OPTIONS:
            self._circle_form_combo.addItem(label, value)
        self._circle_form_combo.currentIndexChanged.connect(self._on_circle_form_changed)
        self.add_widget(form_row("Circle Form", self._circle_form_combo))

        self._gravity_combo = QComboBox()
        self._gravity_combo.setToolTip(
            "Growth direction of each bar. Outward raises away from the ring center (classic circular EQ)."
        )
        for value, label in GRAVITY_OPTIONS:
            self._gravity_combo.addItem(label, value)
        self._gravity_combo.currentIndexChanged.connect(self._on_gravity_changed)
        self.add_widget(form_row("Bar Growth", self._gravity_combo))

        self._blend_combo = QComboBox()
        self._blend_combo.setToolTip(
            "How this layer composites over the background. Additive/Screen make colors brighter and can wash them out."
        )
        for value, label in BLEND_OPTIONS:
            self._blend_combo.addItem(label, value)
        self._blend_combo.currentIndexChanged.connect(self._on_blend_changed)
        self.add_widget(form_row("Blend Mode", self._blend_combo))

        self._attach_note = note_box(
            "Spectrum is attached to the logo core. Use Spectrum Outer Gap in the Logo tab "
            "to control the shared outer radius."
        )
        self._attach_note.hide()
        self.add_widget(self._attach_note)

        toggle_row = QGridLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setHorizontalSpacing(6)
        toggle_row.setVerticalSpacing(6)
        self._toggle_fields = {}
        for index, (field, label) in enumerate(
            (
                ("fillCircle", "Fill Circle"),
                ("solidBand", "Solid Band"),
            )
        ):
            checkbox = QCheckBox(label)
            checkbox.toggled.connect(
                lambda checked, key=field: self.layer_patch_requested.emit({key: checked})
            )
            self._toggle_fields[field] = checkbox
            toggle_row.addWidget(checkbox, index // 2, index % 2)
        toggle_host = QWidget()
        toggle_host.setLayout(toggle_row)
        self.add_widget(toggle_host)

        bar_height_widget, bar_height_setter = build_float_slider(
            "Bar Height (all layers)",
            minimum=0.5,
            maximum=6,
            step=0.05,
            value=1,
            on_change=lambda value: self.draft_patch_requested.emit(
                {"audioBarHeight": round(value, 2)}
            ),
        )
        self._float_setters["audioBarHeight"] = bar_height_setter
        self.add_widget(bar_height_widget)

        for field, label, minimum, maximum, step in (
            ("barCount", "Bar Density (this layer)", 16, 128, 1),
            ("barWidth", "Bar Width (this layer)", 1, 120, 0.25),
            ("thickness", "Spike Height (this layer)", 1, 220, 0.25),
            ("radiusOffset", "Layer Gap / Ring Size (this layer)", 0, 400, 0.5),
            ("opacity", "Opacity (this layer)", 0, 1, 0.01),
            ("glow", "Glow Strength (this layer)", 0, 100, 1),
            ("blur", "Glow Softness (this layer)", 0, 30, 1),
            ("peakCapGap", "Peak Cap Gap (this layer)", 0, 24, 0.25),
            ("peakCapThickness", "Peak Cap Size (this layer)", 1, 16, 0.25),
            ("peakCapDecay", "Peak Cap Decay (this layer)", 0.7, 0.995, 0.005),
        ):
            self.add_widget(self._add_layer_float(field, label, minimum, maximum, step))

        self._peak_caps_enabled = QCheckBox("Peak Caps")
        self._peak_caps_enabled.toggled.connect(
            lambda checked: self.layer_patch_requested.emit({"peakCapsEnabled": checked})
        )
        self.add_widget(self._peak_caps_enabled)

        peak_color_widget, peak_color_setter = build_color_field(
            "Peak Cap Color",
            value="#ffffff",
            on_change=lambda value: self.layer_patch_requested.emit({"peakCapColor": value}),
            parent=self,
        )
        self._peak_cap_color_setter = peak_color_setter
        self.add_widget(peak_color_widget)

        self._color_mode_combo = QComboBox()
        self._color_mode_combo.setToolTip("Color Style")
        self._color_mode_combo.addItem("Solid Color", "solid")
        self._color_mode_combo.addItem("Gradient", "gradient")
        self._color_mode_combo.currentIndexChanged.connect(self._on_color_mode_changed)
        self.add_widget(self._color_mode_combo)

        self._solid_host = QWidget()
        solid_layout = QVBoxLayout(self._solid_host)
        solid_layout.setContentsMargins(0, 0, 0, 0)
        solid_layout.setSpacing(6)
        solid_widget, solid_setter = build_color_field(
            "Color",
            value="#ffffff",
            on_change=lambda value: self.layer_color_patch_requested.emit({"solidColor": value}),
            parent=self,
        )
        self._solid_color_setter = solid_setter
        solid_layout.addWidget(solid_widget)
        self.add_widget(self._solid_host)

        self._gradient_host = QWidget()
        gradient_layout = QVBoxLayout(self._gradient_host)
        gradient_layout.setContentsMargins(0, 0, 0, 0)
        gradient_layout.setSpacing(6)

        self._gradient_direction_combo = QComboBox()
        self._gradient_direction_combo.setToolTip("Gradient Direction")
        for value, label in GRADIENT_DIRECTION_OPTIONS:
            self._gradient_direction_combo.addItem(label, value)
        self._gradient_direction_combo.currentIndexChanged.connect(self._on_gradient_direction_changed)
        gradient_layout.addWidget(self._gradient_direction_combo)

        self._gradient_preset_combo = QComboBox()
        self._gradient_preset_combo.setToolTip("Gradient Preset")
        for value, label in SPECTRUM_GRADIENT_PRESET_OPTIONS:
            self._gradient_preset_combo.addItem(label, value)
        self._gradient_preset_combo.currentIndexChanged.connect(self._on_gradient_preset_changed)
        gradient_layout.addWidget(self._gradient_preset_combo)

        stop_actions = QHBoxLayout()
        stop_actions.setContentsMargins(0, 0, 0, 0)
        add_stop = QPushButton("Add Color")
        add_stop.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        add_stop.clicked.connect(self._add_gradient_stop)
        remove_stop = QPushButton("Remove Last")
        remove_stop.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        remove_stop.clicked.connect(self._remove_gradient_stop)
        stop_actions.addWidget(add_stop)
        stop_actions.addWidget(remove_stop)
        stop_host = QWidget()
        stop_host.setLayout(stop_actions)
        gradient_layout.addWidget(QLabel("Gradient Stops"))
        gradient_layout.addWidget(stop_host)

        self._gradient_stops_host = QWidget()
        self._gradient_stops_layout = QVBoxLayout(self._gradient_stops_host)
        self._gradient_stops_layout.setContentsMargins(0, 0, 0, 0)
        self._gradient_stops_layout.setSpacing(6)
        gradient_layout.addWidget(self._gradient_stops_host)
        self.add_widget(self._gradient_host)
        self._gradient_host.hide()

    def _add_layer_float(
        self,
        field: str,
        label: str,
        minimum: float,
        maximum: float,
        step: float,
    ) -> QWidget:
        def _emit(value: float) -> None:
            payload = value
            if field in {"glow", "blur"}:
                payload = round(value)
            elif field == "barCount":
                payload = int(round(value))
            self.layer_patch_requested.emit({field: payload})

        widget, setter = build_float_slider(
            label,
            minimum=minimum,
            maximum=maximum,
            step=step,
            value=minimum,
            on_change=_emit,
        )
        self._float_setters[field] = setter
        return widget

    def _selected_layer(self) -> dict | None:
        if not self._layers or self._selected_index >= len(self._layers):
            return None
        return self._layers[self._selected_index]

    def _on_layer_combo_changed(self, index: int) -> None:
        if self._binding or index < 0:
            return
        self.layer_selected.emit(index)

    def _on_gravity_changed(self, _index: int) -> None:
        if self._binding:
            return
        value = self._gravity_combo.currentData()
        if isinstance(value, str):
            self.layer_patch_requested.emit({"gravity": value})

    def _on_circle_form_changed(self, _index: int) -> None:
        if self._binding:
            return
        value = str(self._circle_form_combo.currentData() or "linear")
        if value == "full":
            self.layer_patch_requested.emit({"curved": True, "mirrored": True})
        elif value == "semi":
            self.layer_patch_requested.emit({"curved": True, "mirrored": False})
        else:
            self.layer_patch_requested.emit({"curved": False, "mirrored": False})

    @staticmethod
    def _circle_form_from_layer(layer: dict) -> str:
        curved = bool(layer.get("curved"))
        mirrored = bool(layer.get("mirrored"))
        if curved and mirrored:
            return "full"
        if curved:
            return "semi"
        return "linear"

    def _on_blend_changed(self, _index: int) -> None:
        if self._binding:
            return
        value = self._blend_combo.currentData()
        if isinstance(value, str):
            self.layer_patch_requested.emit({"blend_mode": value})

    def _on_color_mode_changed(self, _index: int) -> None:
        if self._binding:
            return
        mode = self._color_mode_combo.currentData()
        if mode == "gradient":
            colors = normalize_spectrum_gradient_colors(
                list(self._color_model.get("gradientColors") or []),
                str(self._color_model.get("solidColor") or "#ffffff"),
            )
            self.layer_color_patch_requested.emit({"mode": "gradient", "gradientColors": colors})
        elif mode == "solid":
            self.layer_color_patch_requested.emit({"mode": "solid"})

    def _on_gradient_direction_changed(self, _index: int) -> None:
        if self._binding:
            return
        value = self._gradient_direction_combo.currentData()
        if isinstance(value, str):
            self.layer_color_patch_requested.emit({"gradientDirection": value})

    def _on_gradient_preset_changed(self, _index: int) -> None:
        if self._binding:
            return
        raw = self._gradient_preset_combo.currentData()
        if not isinstance(raw, str) or not raw:
            return
        colors = [part.strip() for part in raw.split(",") if part.strip()]
        solid = str(self._color_model.get("solidColor") or "#ffffff")
        self.layer_color_patch_requested.emit(
            {"gradientColors": normalize_spectrum_gradient_colors(colors, solid)}
        )

    def _add_gradient_stop(self) -> None:
        colors = list(self._color_model.get("gradientColors") or [])
        if len(colors) >= 5:
            return
        colors.append(colors[-1] if colors else str(self._color_model.get("solidColor") or "#ffffff"))
        self.layer_color_patch_requested.emit(
            {
                "gradientColors": normalize_spectrum_gradient_colors(
                    colors,
                    str(self._color_model.get("solidColor") or "#ffffff"),
                )
            }
        )

    def _remove_gradient_stop(self) -> None:
        colors = list(self._color_model.get("gradientColors") or [])
        if len(colors) <= 2:
            return
        self.layer_color_patch_requested.emit(
            {
                "gradientColors": normalize_spectrum_gradient_colors(
                    colors[:-1],
                    str(self._color_model.get("solidColor") or "#ffffff"),
                )
            }
        )

    def _rebuild_gradient_stops(self, colors: list[str]) -> None:
        if self._gradient_stops_host is None:
            return
        while self._gradient_stops_layout.count():
            item = self._gradient_stops_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._gradient_stop_setters.clear()

        for index, color in enumerate(colors):
            widget, setter = build_color_field(
                f"Stop {index + 1}",
                value=color,
                on_change=lambda value, stop_index=index: self._patch_gradient_stop(stop_index, value),
                parent=self,
            )
            self._gradient_stop_setters.append(setter)
            self._gradient_stops_layout.addWidget(widget)

    def _patch_gradient_stop(self, stop_index: int, value: str) -> None:
        colors = list(self._color_model.get("gradientColors") or [])
        if stop_index >= len(colors):
            return
        colors[stop_index] = value
        self.layer_color_patch_requested.emit({"gradientColors": colors})

    def bind_state(
        self,
        draft: dict,
        layers: list[dict],
        *,
        selected_index: int,
        attached_to_logo: bool,
    ) -> None:
        self._binding = True
        try:
            self._layers = layers
            self._selected_index = max(0, min(selected_index, max(len(layers) - 1, 0)))
            layer = self._selected_layer()

            if self._attach_note is not None:
                self._attach_note.setVisible(attached_to_logo)

            self._layer_combo.blockSignals(True)
            self._layer_combo.clear()
            for index, item in enumerate(layers):
                name = str(item.get("name") or "").strip() or f"Layer {index + 1}"
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

            gravity = str(layer.get("gravity") or "normal")
            blend = str(layer.get("blend_mode") or "normal")
            circle_form = self._circle_form_from_layer(layer)
            circle_index = self._circle_form_combo.findData(circle_form)
            if circle_index >= 0:
                self._circle_form_combo.setCurrentIndex(circle_index)
            gravity_index = self._gravity_combo.findData(gravity)
            if gravity_index >= 0:
                self._gravity_combo.setCurrentIndex(gravity_index)
            blend_index = self._blend_combo.findData(blend)
            if blend_index >= 0:
                self._blend_combo.setCurrentIndex(blend_index)

            for field, checkbox in self._toggle_fields.items():
                checkbox.setChecked(bool(layer.get(field)))

            if "audioBarHeight" in self._float_setters:
                self._float_setters["audioBarHeight"](float(draft.get("audioBarHeight") or 1))

            layer_defaults = {
                "barCount": 64.0,
                "barWidth": 5.0,
                "thickness": 36.0,
                "radiusOffset": 0.0,
                "opacity": 1.0,
                "glow": 0.0,
                "blur": 0.0,
                "peakCapGap": 4.0,
                "peakCapThickness": 3.0,
                "peakCapDecay": 0.92,
            }
            for field, default in layer_defaults.items():
                if field not in self._float_setters:
                    continue
                raw = layer.get(field)
                if isinstance(raw, (int, float)):
                    self._float_setters[field](float(raw))
                else:
                    self._float_setters[field](float(default))
            self._peak_caps_enabled.setChecked(bool(layer.get("peakCapsEnabled", False)))
            self._peak_cap_color_setter(str(layer.get("peakCapColor") or "#ffffff"))

            self._color_model = extract_spectrum_layer_color_model(
                layer,
                get_spectrum_layer_color_fallback(self._selected_index),
            )
            mode = str(self._color_model.get("mode") or "solid")
            mode_index = self._color_mode_combo.findData(mode)
            if mode_index >= 0:
                self._color_mode_combo.setCurrentIndex(mode_index)

            is_gradient = mode == "gradient"
            if self._gradient_host is not None:
                self._gradient_host.setVisible(is_gradient)
            if self._solid_host is not None:
                self._solid_host.setVisible(not is_gradient)

            if self._solid_color_setter is not None:
                self._solid_color_setter(str(self._color_model.get("solidColor") or "#ffffff"))

            direction = str(self._color_model.get("gradientDirection") or "left-to-right")
            direction_index = self._gradient_direction_combo.findData(direction)
            if direction_index >= 0:
                self._gradient_direction_combo.setCurrentIndex(direction_index)

            gradient_colors = list(self._color_model.get("gradientColors") or [])
            preset_value = build_spectrum_gradient_preset_value(gradient_colors)
            preset_index = self._gradient_preset_combo.findData(preset_value)
            self._gradient_preset_combo.blockSignals(True)
            if preset_index >= 0:
                self._gradient_preset_combo.setCurrentIndex(preset_index)
            else:
                self._gradient_preset_combo.setCurrentIndex(-1)
            self._gradient_preset_combo.blockSignals(False)

            self._rebuild_gradient_stops(gradient_colors)
        finally:
            self._binding = False
