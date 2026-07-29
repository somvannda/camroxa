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

from features.video.lib.spectrum_audio_dial import (
    FLYING_GLOW_WING_SPEED_DIAL_MAX,
    SPECTRUM_AUDIO_DIAL_MAX,
    from_spectrum_audio_dial,
    to_spectrum_audio_dial,
)
from features.video.lib.spectrum_style_registry import (
    ANCHOR_OPTIONS,
    SPECTRUM_PRESET_OPTIONS,
    STACKED_SPECTRUM_PRESET_OPTIONS,
    build_stacked_spectrum_preset_template,
)
from features.video.widgets.inspector_fields import InspectorSection
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

    _AUDIO_FIELDS: tuple[tuple[str, float, float, int], ...] = (
        ("audioInputGain", 1, 10, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioKickImpact", 0, 5, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioBassEmphasis", 0.35, 4, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioBandContrast", 0.35, 5, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioTransientFocus", 0.35, 4, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioTrebleShimmer", 0.35, 4, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioPeakHoldBlend", 0, 1, SPECTRUM_AUDIO_DIAL_MAX),
        ("audioMotionSmoothing", 0, 0.99, SPECTRUM_AUDIO_DIAL_MAX),
        ("flyingGlowWingMotionSpeed", 0.5, 20, FLYING_GLOW_WING_SPEED_DIAL_MAX),
        ("flyingGlowWingRelease", 0, 4, SPECTRUM_AUDIO_DIAL_MAX),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._spectrum_toggle: QCheckBox | None = None
        self._preset_combo: QComboBox | None = None
        self._selected_preset_key: str | None = None
        self._previous_preset_key: str | None = None
        self._anchor_combo: QComboBox | None = None
        self._layer_editor: SpectrumLayerEditor | None = None
        self._flying_glow_host: QWidget | None = None
        self._position_x_slider: QSlider | None = None
        self._position_y_slider: QSlider | None = None
        self._position_x_label: QLabel | None = None
        self._position_y_label: QLabel | None = None
        self._audio_sliders: dict[str, tuple[QSlider, QLabel, float, float, int]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        spectrum_section = InspectorSection("")
        self._spectrum_toggle = QCheckBox("Enable Spectrum")
        self._spectrum_toggle.toggled.connect(
            lambda checked: self._emit_patch({"spectrumEnabled": checked})
        )
        spectrum_section.add_widget(self._spectrum_toggle)

        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("Preset")
        for value, label in SPECTRUM_PRESET_OPTIONS:
            self._preset_combo.addItem(label, value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_index_changed)
        spectrum_section.add_widget(self._preset_combo)

        preset_restore_row = QHBoxLayout()
        preset_restore_row.setContentsMargins(0, 0, 0, 0)
        preset_restore_row.addStretch()
        spectrum_restore_btn = QPushButton("Restore original")
        spectrum_restore_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        spectrum_restore_btn.setToolTip("Reset the selected spectrum preset to factory defaults (local JSON override only).")
        spectrum_restore_btn.clicked.connect(self.preset_restore_requested.emit)
        preset_restore_row.addWidget(spectrum_restore_btn)
        preset_restore_host = QWidget()
        preset_restore_host.setLayout(preset_restore_row)
        spectrum_section.add_widget(preset_restore_host)

        stack_row = QHBoxLayout()
        stack_row.setContentsMargins(0, 0, 0, 0)
        stack_row.setSpacing(6)
        self._stack_preset_combo = QComboBox()
        self._stack_preset_combo.setToolTip("Stacked Ring Preset")
        self._stack_preset_combo.addItem("Pick stacked preset...", "")
        for value, label in STACKED_SPECTRUM_PRESET_OPTIONS:
            self._stack_preset_combo.addItem(label, value)
        stack_row.addWidget(self._stack_preset_combo, 1)
        apply_stack_btn = QPushButton("Apply")
        apply_stack_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        apply_stack_btn.clicked.connect(self._on_apply_stack_preset)
        stack_row.addWidget(apply_stack_btn)
        clear_stack_btn = QPushButton("Clear")
        clear_stack_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        clear_stack_btn.clicked.connect(self.stacked_preset_clear_requested.emit)
        stack_row.addWidget(clear_stack_btn)
        stack_host = QWidget()
        stack_host.setLayout(stack_row)
        spectrum_section.add_widget(stack_host)
        root.addWidget(spectrum_section)

        audio_section = InspectorSection("Audio")
        for field, minimum, maximum, dial_max in self._AUDIO_FIELDS[:3]:
            audio_section.add_widget(self._build_audio_slider(field, minimum, maximum, dial_max))

        advanced = InspectorSection(
            "Advanced",
            subtitle="Separation, shimmer, tail, and smoothing controls.",
        )
        for field, minimum, maximum, dial_max in self._AUDIO_FIELDS[3:8]:
            advanced.add_widget(self._build_audio_slider(field, minimum, maximum, dial_max))

        self._flying_glow_host = QWidget()
        flying_layout = QVBoxLayout(self._flying_glow_host)
        flying_layout.setContentsMargins(0, 0, 0, 0)
        flying_layout.setSpacing(8)
        for field, minimum, maximum, dial_max in self._AUDIO_FIELDS[8:]:
            flying_layout.addWidget(self._build_audio_slider(field, minimum, maximum, dial_max))
        self._flying_glow_host.hide()
        advanced.add_widget(self._flying_glow_host)
        audio_section.add_widget(advanced)
        root.addWidget(audio_section)

        position_section = InspectorSection(
            "Positioning",
            subtitle="Move the spectrum and logo anchor around the preview.",
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

    def set_preset_options(self, options: tuple[tuple[str, str], ...]) -> None:
        if self._preset_combo is None:
            return
        current_style = self._preset_combo.currentData()
        self._binding = True
        try:
            self._preset_combo.clear()
            for value, label in options:
                self._preset_combo.addItem(label, value)
            if isinstance(current_style, str):
                index = self._preset_combo.findData(current_style)
                if index >= 0:
                    self._preset_combo.setCurrentIndex(index)
        finally:
            self._binding = False

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
            "audioKickImpact": "Kick Impact",
            "audioBassEmphasis": "Bass Emphasis",
            "audioBandContrast": "Band Contrast",
            "audioTransientFocus": "Transient Focus",
            "audioTrebleShimmer": "Treble Shimmer",
            "audioPeakHoldBlend": "Peak Hold Blend",
            "audioMotionSmoothing": "Motion Smoothing",
            "flyingGlowWingMotionSpeed": "Flying Glow Wing Speed",
            "flyingGlowWingRelease": "Flying Glow Wing Release",
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

    def _on_preset_index_changed(self, _index: int) -> None:
        if self._binding or self._preset_combo is None:
            return
        preset = self._preset_combo.currentData()
        if isinstance(preset, str):
            self._previous_preset_key = self._selected_preset_key
            self._selected_preset_key = preset
            self.preset_apply_requested.emit(preset)

    def selected_preset_key(self) -> str | None:
        if self._preset_combo is not None:
            current = self._preset_combo.currentData()
            if isinstance(current, str) and current:
                return current
        return self._selected_preset_key

    def previous_preset_key(self) -> str | None:
        return self._previous_preset_key

    def _on_apply_stack_preset(self) -> None:
        if self._binding or self._stack_preset_combo is None:
            return
        preset = self._stack_preset_combo.currentData()
        if isinstance(preset, str) and preset.strip():
            self.stacked_preset_apply_requested.emit(preset)

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

    def bind_draft(
        self,
        draft: dict,
        *,
        layers: list[dict],
        selected_layer_index: int,
    ) -> None:
        self._binding = True
        try:
            style = str(draft.get("style") or "orbit-spikes")
            if self._flying_glow_host is not None:
                # Ignition Flare (+ legacy neon-pulse packs) expose wing motion dials.
                self._flying_glow_host.setVisible(style in {"ignition-flare", "neon-pulse"})

            if self._layer_editor is not None:
                self._layer_editor.bind_state(
                    draft,
                    layers,
                    selected_index=selected_layer_index,
                    attached_to_logo=bool(draft.get("spectrumAttachToLogo")),
                )

            if self._spectrum_toggle is not None:
                self._spectrum_toggle.setChecked(bool(draft.get("spectrumEnabled", True)))

            if self._preset_combo is not None:
                index = self._preset_combo.findData(style)
                if index >= 0:
                    self._preset_combo.setCurrentIndex(index)
                current = self._preset_combo.currentData()
                if isinstance(current, str) and current:
                    self._selected_preset_key = current
                    if self._previous_preset_key is None:
                        self._previous_preset_key = current

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
