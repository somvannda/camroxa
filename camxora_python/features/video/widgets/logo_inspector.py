"""Logo domain inspector — Phase 9b."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from features.video.lib.logo_settings import (
    LOGO_MOTION_OPTIONS,
    LOGO_SHAPE_OPTIONS,
    LOGO_SPIN_DIRECTION_OPTIONS,
)
from features.video.lib.logo_style_registry import LOGO_STYLE_PRESETS
from features.video.widgets.inspector_fields import (
    InspectorSection,
    build_float_slider,
)
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row, note_box


class LogoInspector(QWidget):
    draft_patch_requested = Signal(dict)
    preset_apply_requested = Signal(str)
    preset_restore_requested = Signal()
    logo_shape_apply_requested = Signal(str)
    logo_size_apply_requested = Signal(float)
    spectrum_attach_toggle_requested = Signal(bool)
    spectrum_logo_gap_requested = Signal(float)
    select_logo_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._logo_path_input: QLineEdit | None = None
        self._preset_combo: QComboBox | None = None
        self._selected_preset_key: str | None = None
        self._previous_preset_key: str | None = None
        self._shape_combo: QComboBox | None = None
        self._spin_direction_combo: QComboBox | None = None
        self._motion_combo: QComboBox | None = None
        self._spin_speed_slider: QSlider | None = None
        self._spin_speed_label: QLabel | None = None
        self._float_setters: dict[str, Callable[[float], None]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Logo",
            subtitle="Shape, scale, opacity, and logo-specific audio motion from the Python video settings route.",
        )
        toggles = QHBoxLayout()
        toggles.setContentsMargins(0, 0, 0, 0)
        self._logo_enabled = QCheckBox("Logo")
        self._logo_enabled.toggled.connect(lambda checked: self._emit_patch({"logoEnabled": checked}))
        self._spin_enabled = QCheckBox("Spin")
        self._spin_enabled.toggled.connect(lambda checked: self._emit_patch({"logoSpinEnabled": checked}))
        toggle_host = QWidget()
        toggle_host.setLayout(toggles)
        toggles.addWidget(self._logo_enabled)
        toggles.addWidget(self._spin_enabled)
        toggles.addStretch()
        section.add_widget(toggle_host)

        self._spin_direction_combo = QComboBox()
        for value, label in LOGO_SPIN_DIRECTION_OPTIONS:
            self._spin_direction_combo.addItem(label, value)
        self._spin_direction_combo.currentIndexChanged.connect(self._on_spin_direction_changed)
        section.add_widget(form_row("Direction", self._spin_direction_combo))
        section.add_widget(self._build_spin_speed_row())

        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("Preset look")
        for value, label in LOGO_STYLE_PRESETS:
            self._preset_combo.addItem(label, value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_index_changed)
        section.add_widget(form_row("Preset Look", self._preset_combo))

        preset_restore_row = QHBoxLayout()
        preset_restore_row.addStretch()
        logo_restore_btn = QPushButton("Restore original")
        logo_restore_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        logo_restore_btn.setToolTip("Reset this preset look to factory defaults (keeps your video template Save separate).")
        logo_restore_btn.clicked.connect(self.preset_restore_requested.emit)
        preset_restore_row.addWidget(logo_restore_btn)
        logo_restore_host = QWidget()
        logo_restore_host.setLayout(preset_restore_row)
        section.add_widget(logo_restore_host)
        section.add_widget(
            note_box(
                "Preset tweaks are saved locally and survive app restart. "
                "Restore original clears only this preset look. Save still writes the current look to the video template."
            )
        )

        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(8)
        self._logo_path_input = QLineEdit()
        self._logo_path_input.setReadOnly(True)
        self._logo_path_input.setPlaceholderText("C:/path/to/logo.png")
        select_btn = QPushButton("Select Logo")
        select_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        select_btn.clicked.connect(self.select_logo_requested.emit)
        file_row.addWidget(self._logo_path_input, stretch=1)
        file_row.addWidget(select_btn)
        file_host = QWidget()
        file_host.setLayout(file_row)
        section.add_widget(form_row("File", file_host))

        self._shape_combo = QComboBox()
        for value, label in LOGO_SHAPE_OPTIONS:
            self._shape_combo.addItem(label, value)
        self._shape_combo.currentIndexChanged.connect(self._on_shape_changed)
        section.add_widget(form_row("Shape", self._shape_combo))

        size_widget, size_setter = build_float_slider(
            "Size",
            minimum=1,
            maximum=10,
            step=0.05,
            value=2,
            on_change=lambda value: self.logo_size_apply_requested.emit(value),
            format_value=lambda value: f"{value:.2f} => {round(value * 100)}px",
        )
        self._float_setters["logoSizeStep"] = size_setter
        section.add_widget(size_widget)

        self._attach_toggle = QCheckBox("Attach to Logo")
        self._attach_toggle.toggled.connect(self.spectrum_attach_toggle_requested.emit)
        section.add_widget(self._attach_toggle)
        section.add_widget(
            note_box("Keep the spectrum ring locked outside the logo when both layers are active.")
        )

        gap_widget, gap_setter = build_float_slider(
            "Spectrum Outer Gap",
            minimum=0,
            maximum=96,
            step=0.5,
            value=0,
            on_change=lambda value: self.spectrum_logo_gap_requested.emit(value),
            format_value=lambda value: f"{value:.1f}px",
        )
        self._float_setters["spectrumLogoGap"] = gap_setter
        section.add_widget(gap_widget)
        section.add_widget(
            note_box("Controls the space between the logo edge and the first spectrum ring while attached.")
        )

        for field, label, minimum, maximum, step in (
            ("logoOpacity", "Opacity", 0, 1, 0.01),
            ("logoReactivity", "Audio Reactivity", 0, 2, 0.01),
            ("logoSmoothing", "Reaction Smoothness", 0, 0.99, 0.01),
        ):
            widget, setter = build_float_slider(
                label,
                minimum=minimum,
                maximum=maximum,
                step=step,
                value=minimum,
                on_change=lambda value, key=field: self._emit_patch({key: value}),
            )
            self._float_setters[field] = setter
            section.add_widget(widget)

        self._motion_combo = QComboBox()
        for value, label in LOGO_MOTION_OPTIONS:
            self._motion_combo.addItem(label, value)
        self._motion_combo.currentIndexChanged.connect(self._on_motion_changed)
        section.add_widget(form_row("Motion", self._motion_combo))

        for field, label, minimum, maximum, step in (
            ("logoMotionZoomStrength", "Zoom Strength", 0, 20, 0.05),
            ("logoMotionVibrateStrength", "Vibrate Strength", 0, 20, 0.05),
            ("logoMotionSpeed", "Motion Speed", 0, 20, 0.05),
        ):
            widget, setter = build_float_slider(
                label,
                minimum=minimum,
                maximum=maximum,
                step=step,
                value=minimum,
                on_change=lambda value, key=field: self._emit_patch({key: value}),
            )
            self._float_setters[field] = setter
            section.add_widget(widget)

        root.addWidget(section)
        root.addStretch()

    def _build_spin_speed_row(self) -> QWidget:
        from PySide6.QtCore import Qt

        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._spin_speed_label = QLabel("Speed (0°/s)")
        self._spin_speed_label.setObjectName(SUBTITLE_LABEL_ID)
        self._spin_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._spin_speed_slider.setMinimum(0)
        self._spin_speed_slider.setMaximum(72)
        self._spin_speed_slider.valueChanged.connect(self._on_spin_speed_changed)
        layout.addWidget(self._spin_speed_label)
        layout.addWidget(self._spin_speed_slider)
        return host

    def _on_preset_index_changed(self, _index: int) -> None:
        if self._binding or self._preset_combo is None:
            return
        preset = self._preset_combo.currentData()
        if isinstance(preset, str) and preset:
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

    def set_preset_options(self, options: tuple[tuple[str, str], ...]) -> None:
        if self._preset_combo is None:
            return
        current = self._preset_combo.currentData()
        self._binding = True
        try:
            self._preset_combo.clear()
            for value, label in options:
                self._preset_combo.addItem(label, value)
            if isinstance(current, str):
                index = self._preset_combo.findData(current)
                if index >= 0:
                    self._preset_combo.setCurrentIndex(index)
        finally:
            self._binding = False

    def _on_spin_speed_changed(self, raw: int) -> None:
        speed = raw * 10
        if self._spin_speed_label is not None:
            self._spin_speed_label.setText(f"Speed ({speed}°/s)")
        self._emit_patch({"logoSpinSpeed": float(speed)})

    def _on_shape_changed(self, _index: int) -> None:
        if self._binding or self._shape_combo is None:
            return
        value = self._shape_combo.currentData()
        if isinstance(value, str):
            self.logo_shape_apply_requested.emit(value)

    def _on_spin_direction_changed(self, _index: int) -> None:
        if self._binding or self._spin_direction_combo is None:
            return
        value = self._spin_direction_combo.currentData()
        if isinstance(value, str):
            self._emit_patch({"logoSpinDirection": value})

    def _on_motion_changed(self, _index: int) -> None:
        if self._binding or self._motion_combo is None:
            return
        value = self._motion_combo.currentData()
        if isinstance(value, str):
            self._emit_patch({"logoMotionMode": value})

    def _emit_patch(self, patch: dict) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(patch)

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        try:
            self._logo_enabled.setChecked(bool(draft.get("logoEnabled", True)))
            self._spin_enabled.setChecked(bool(draft.get("logoSpinEnabled")))
            if self._logo_path_input is not None:
                self._logo_path_input.setText(str(draft.get("logoPath") or ""))

            if self._shape_combo is not None:
                index = self._shape_combo.findData(str(draft.get("logoShape") or "circle"))
                if index >= 0:
                    self._shape_combo.setCurrentIndex(index)
            if self._spin_direction_combo is not None:
                index = self._spin_direction_combo.findData(str(draft.get("logoSpinDirection") or "cw"))
                if index >= 0:
                    self._spin_direction_combo.setCurrentIndex(index)
            if self._motion_combo is not None:
                index = self._motion_combo.findData(str(draft.get("logoMotionMode") or "none"))
                if index >= 0:
                    self._motion_combo.setCurrentIndex(index)

            spin_speed = int(round(float(draft.get("logoSpinSpeed") or 0)))
            if self._spin_speed_slider is not None:
                self._spin_speed_slider.setValue(max(0, min(72, spin_speed // 10)))
            if self._spin_speed_label is not None:
                self._spin_speed_label.setText(f"Speed ({spin_speed}°/s)")

            self._attach_toggle.setChecked(bool(draft.get("spectrumAttachToLogo")))

            for field, setter in self._float_setters.items():
                setter(float(draft.get(field, 0)))
        finally:
            self._binding = False

    def mount_effect_pack_selector(self, selector: QWidget) -> None:
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(0, selector)
