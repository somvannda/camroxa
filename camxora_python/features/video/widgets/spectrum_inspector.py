"""Spectrum domain inspector — Phase 9b."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.composition_draft import composition_axis_options
from features.video.lib.spectrum_audio_dial import (
    SPECTRUM_AUDIO_DIAL_MAX,
    from_spectrum_audio_dial,
    to_spectrum_audio_dial,
)
from features.video.lib.spectrum_style_registry import (
    ANCHOR_OPTIONS,
)
from features.video.widgets.inspector_fields import InspectorSection
from features.video.widgets.spectrum_instance_editor import SpectrumInstanceEditor
from features.video.widgets.spectrum_layer_editor import SpectrumLayerEditor
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID

class SpectrumInspector(QWidget):
    draft_patch_requested = Signal(dict)
    preset_apply_requested = Signal(str)
    preset_restore_requested = Signal()
    stacked_preset_apply_requested = Signal(str)
    stacked_preset_clear_requested = Signal()
    layer_patch_requested = Signal(dict)
    layer_color_patch_requested = Signal(dict)
    layer_add_requested = Signal()
    layer_duplicate_requested = Signal()
    layer_delete_requested = Signal()
    layer_move_up_requested = Signal()
    layer_move_down_requested = Signal()
    layer_selected = Signal(int)
    instance_selected = Signal(int)
    instance_add_requested = Signal()
    instance_duplicate_requested = Signal()
    instance_delete_requested = Signal()
    instance_move_up_requested = Signal()
    instance_move_down_requested = Signal()
    instance_patch_requested = Signal(dict)

    _AUDIO_FIELDS: tuple[tuple[str, float, float, int], ...] = (
        ("audioInputGain", 1, 10, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioMotionSmoothing", 0, 0.99, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioPeakHoldBlend", 0, 1, SPECTRUM_AUDIO_DIAL_MAX),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._spectrum_toggle: QCheckBox | None = None
        self._shape_combo: QComboBox | None = None
        self._material_combo: QComboBox | None = None
        self._animation_combo: QComboBox | None = None
        self._palette_combo: QComboBox | None = None
        self._anchor_combo: QComboBox | None = None
        self._layer_editor: SpectrumLayerEditor | None = None
        self._position_x_slider: QSlider | None = None
        self._position_y_slider: QSlider | None = None
        self._position_x_label: QLabel | None = None
        self._position_y_label: QLabel | None = None
        self._audio_sliders: dict[str, tuple[QSlider, QLabel, float, float, int]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        self._instance_editor = SpectrumInstanceEditor(self)
        self._instance_editor.instance_selected.connect(self.instance_selected.emit)
        self._instance_editor.instance_add_requested.connect(self.instance_add_requested.emit)
        self._instance_editor.instance_duplicate_requested.connect(self.instance_duplicate_requested.emit)
        self._instance_editor.instance_delete_requested.connect(self.instance_delete_requested.emit)
        self._instance_editor.instance_move_up_requested.connect(self.instance_move_up_requested.emit)
        self._instance_editor.instance_move_down_requested.connect(self.instance_move_down_requested.emit)
        self._instance_editor.instance_patch_requested.connect(self.instance_patch_requested.emit)
        root.addWidget(self._instance_editor)

        spectrum_section = InspectorSection("Composition Axes")
        self._spectrum_toggle = QCheckBox("Enable Spectrum")
        self._spectrum_toggle.toggled.connect(
            lambda checked: self._emit_patch({"spectrumEnabled": checked})
        )
        spectrum_section.add_widget(self._spectrum_toggle)

        axes = composition_axis_options()
        self._shape_combo = QComboBox()
        self._shape_combo.setToolTip("Shape (geometry)")
        self._shape_combo.addItem("None", "none")
        for value, label in axes["shapes"]:
            self._shape_combo.addItem(label, value)
        self._shape_combo.currentIndexChanged.connect(
            lambda: self._emit_axis("compositionSpectrumShape", self._shape_combo)
        )
        spectrum_section.add_widget(self._labeled_combo("Shape", self._shape_combo))

        self._material_combo = QComboBox()
        self._material_combo.setToolTip("Material (look)")
        self._material_combo.addItem("None", "none")
        for value, label in axes["materials"]:
            self._material_combo.addItem(label, value)
        self._material_combo.currentIndexChanged.connect(
            lambda: self._emit_axis("compositionSpectrumMaterial", self._material_combo)
        )
        spectrum_section.add_widget(self._labeled_combo("Material", self._material_combo))

        self._animation_combo = QComboBox()
        self._animation_combo.setToolTip("Animation behavior")
        self._animation_combo.addItem("None", "none")
        for value, label in axes["animations"]:
            self._animation_combo.addItem(label, value)
        self._animation_combo.currentIndexChanged.connect(
            lambda: self._emit_axis("compositionSpectrumAnimation", self._animation_combo)
        )
        spectrum_section.add_widget(self._labeled_combo("Animation", self._animation_combo))

        self._palette_combo = QComboBox()
        self._palette_combo.setToolTip("Color palette")
        self._palette_combo.addItem("None", "none")
        for value, label in axes["palettes"]:
            self._palette_combo.addItem(label, value)
        self._palette_combo.currentIndexChanged.connect(
            lambda: self._emit_axis("compositionColorPalette", self._palette_combo)
        )
        spectrum_section.add_widget(self._labeled_combo("Palette", self._palette_combo))
        root.addWidget(spectrum_section)

        audio_section = InspectorSection(
            "Audio",
            subtitle="Global spectrum response. Layer colors/glow live in Layers below.",
        )
        for field, minimum, maximum, dial_max in self._AUDIO_FIELDS:
            audio_section.add_widget(self._build_audio_slider(field, minimum, maximum, dial_max))
        root.addWidget(audio_section)

        position_section = InspectorSection(
            "Positioning",
            subtitle=(
                "Moves the spectrum only. Logo stays centered unless Attach Spectrum to Logo "
                "is enabled in the Logo tab (then both move together)."
            ),
        )
        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_label = QLabel("Spectrum Position")
        reset_label.setObjectName(SUBTITLE_LABEL_ID)
        reset_btn = QPushButton("Reset Center")
        reset_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        reset_btn.clicked.connect(
            lambda: self._emit_patch({"anchor": "center", "positionX": 0, "positionY": 0})
        )
        reset_row.addWidget(reset_label)
        reset_row.addStretch()
        reset_row.addWidget(reset_btn)
        reset_host = QWidget()
        reset_host.setLayout(reset_row)
        position_section.add_widget(reset_host)

        self._anchor_combo = QComboBox()
        self._anchor_combo.setToolTip("Anchor")
        for value, label in ANCHOR_OPTIONS:
            self._anchor_combo.addItem(label, value)
        self._anchor_combo.currentIndexChanged.connect(self._on_anchor_changed)
        position_section.add_widget(self._anchor_combo)

        self._position_x_label, self._position_x_slider = self._build_position_slider("X Offset")
        self._position_y_label, self._position_y_slider = self._build_position_slider("Y Offset")
        self._position_x_slider.valueChanged.connect(
            lambda value: self._emit_patch({"positionX": float(value)})
        )
        self._position_y_slider.valueChanged.connect(
            lambda value: self._emit_patch({"positionY": float(value)})
        )
        position_section.add_widget(self._position_slider_host(self._position_x_label, self._position_x_slider))
        position_section.add_widget(self._position_slider_host(self._position_y_label, self._position_y_slider))
        root.addWidget(position_section)

        self._layer_editor = SpectrumLayerEditor()
        self._layer_editor.draft_patch_requested.connect(self.draft_patch_requested.emit)
        self._layer_editor.layer_patch_requested.connect(self.layer_patch_requested.emit)
        self._layer_editor.layer_color_patch_requested.connect(self.layer_color_patch_requested.emit)
        self._layer_editor.layer_add_requested.connect(self.layer_add_requested.emit)
        self._layer_editor.layer_duplicate_requested.connect(self.layer_duplicate_requested.emit)
        self._layer_editor.layer_delete_requested.connect(self.layer_delete_requested.emit)
        self._layer_editor.layer_move_up_requested.connect(self.layer_move_up_requested.emit)
        self._layer_editor.layer_move_down_requested.connect(self.layer_move_down_requested.emit)
        self._layer_editor.layer_selected.connect(self.layer_selected.emit)
        root.addWidget(self._layer_editor)
        root.addStretch()

    def mount_effect_pack_selector(self, selector: QWidget) -> None:
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(0, selector)

    @staticmethod
    def _labeled_combo(title: str, combo: QComboBox) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(title)
        label.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(label)
        layout.addWidget(combo)
        return host

    def _emit_axis(self, key: str, combo: QComboBox | None) -> None:
        if self._binding or combo is None:
            return
        value = combo.currentData()
        if isinstance(value, str):
            self._emit_patch({key: value})

    def set_preset_options(self, options: tuple[tuple[str, str], ...]) -> None:
        # Legacy preset dropdown removed — composition axes are the catalog UI.
        _ = options

    def _build_audio_slider(
        self,
        field: str,
        minimum: float,
        maximum: float,
        dial_max: int,
    ) -> QWidget:
        host = QWidget()
        host.setAutoFillBackground(False)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel("")
        label.setObjectName(SUBTITLE_LABEL_ID)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setAutoFillBackground(False)
        slider.setMinimum(0)
        slider.setMaximum(dial_max)

        def _emit(raw: int) -> None:
            label.setText(f"{self._audio_label(field)} ({raw})")
            self._emit_patch(
                {field: from_spectrum_audio_dial(raw, minimum, maximum, dial_max)}
            )

        slider.valueChanged.connect(_emit)
        layout.addWidget(label)
        layout.addWidget(slider)
        self._audio_sliders[field] = (slider, label, minimum, maximum, dial_max)
        return host

    @staticmethod
    def _audio_label(field: str) -> str:
        labels = {
            "audioInputGain": "Input Gain",
            "audioPeakHoldBlend": "Peak Hold Blend",
            "audioMotionSmoothing": "Motion Smoothing",
        }
        return labels.get(field, field)

    @staticmethod
    def _build_position_slider(title: str) -> tuple[QLabel, QSlider]:
        label = QLabel(f"{title} (0)")
        label.setObjectName(SUBTITLE_LABEL_ID)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(-1000)
        slider.setMaximum(1000)

        def _update(value: int) -> None:
            label.setText(f"{title} ({value})")

        slider.valueChanged.connect(_update)
        return label, slider

    @staticmethod
    def _position_slider_host(label: QLabel, slider: QSlider) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label)
        layout.addWidget(slider)
        return host

    def selected_preset_key(self) -> str | None:
        if self._shape_combo is not None:
            current = self._shape_combo.currentData()
            if isinstance(current, str) and current:
                return current
        return None

    def previous_preset_key(self) -> str | None:
        return None

    def _on_anchor_changed(self, _index: int) -> None:
        if self._binding or self._anchor_combo is None:
            return
        anchor = self._anchor_combo.currentData()
        if isinstance(anchor, str):
            self._emit_patch({"anchor": anchor})

    def _emit_patch(self, patch: dict) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(patch)

    def _set_combo_value(self, combo: QComboBox | None, value: str) -> None:
        if combo is None:
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def bind_draft(
        self,
        draft: dict,
        *,
        layers: list[dict],
        selected_layer_index: int,
        instances: list[dict] | None = None,
        selected_instance_index: int = 0,
    ) -> None:
        self._binding = True
        try:
            if getattr(self, "_instance_editor", None) is not None and instances is not None:
                self._instance_editor.bind_instances(
                    instances,
                    selected_index=selected_instance_index,
                )

            if self._layer_editor is not None:
                self._layer_editor.bind_state(
                    draft,
                    layers,
                    selected_index=selected_layer_index,
                    attached_to_logo=bool(draft.get("spectrumAttachToLogo")),
                )

            if self._spectrum_toggle is not None:
                self._spectrum_toggle.setChecked(bool(draft.get("spectrumEnabled", True)))

            self._set_combo_value(
                self._shape_combo,
                str(draft.get("compositionSpectrumShape") or "none"),
            )
            self._set_combo_value(
                self._material_combo,
                str(draft.get("compositionSpectrumMaterial") or "none"),
            )
            self._set_combo_value(
                self._animation_combo,
                str(draft.get("compositionSpectrumAnimation") or "none"),
            )
            self._set_combo_value(
                self._palette_combo,
                str(draft.get("compositionColorPalette") or "none"),
            )

            if self._anchor_combo is not None:
                anchor = str(draft.get("anchor") or "center")
                index = self._anchor_combo.findData(anchor)
                if index >= 0:
                    self._anchor_combo.setCurrentIndex(index)

            for field, (slider, label, minimum, maximum, dial_max) in self._audio_sliders.items():
                dial = to_spectrum_audio_dial(float(draft.get(field, minimum)), minimum, maximum, dial_max)
                label.setText(f"{self._audio_label(field)} ({dial})")
                slider.setValue(dial)

            position_x = int(round(float(draft.get("positionX", 0))))
            position_y = int(round(float(draft.get("positionY", 0))))
            if self._position_x_slider is not None and self._position_x_label is not None:
                self._position_x_slider.setValue(position_x)
                self._position_x_label.setText(f"X Offset ({position_x})")
            if self._position_y_slider is not None and self._position_y_label is not None:
                self._position_y_slider.setValue(position_y)
                self._position_y_label.setText(f"Y Offset ({position_y})")
        finally:
            self._binding = False
