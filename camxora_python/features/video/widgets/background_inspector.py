"""Background domain inspector — Phase 9b."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_controls import StudioCheckBox

from features.video.lib.background_settings import BACKGROUND_FIT_OPTIONS, BACKGROUND_MOTION_OPTIONS
from features.video.lib.background_style_registry import BACKGROUND_STYLE_PRESETS
from features.video.widgets.inspector_fields import (
    InspectorSection,
    build_color_field,
    build_float_slider,
)
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID
from shared.widgets.settings_ui import form_row, note_box


class BackgroundInspector(QWidget):
    draft_patch_requested = Signal(dict)
    preset_apply_requested = Signal(str)
    preset_restore_requested = Signal()
    reset_transform_requested = Signal()
    select_background_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._enabled_toggle: QCheckBox | None = None
        self._details_host: QWidget | None = None
        self._preset_combo: QComboBox | None = None
        self._selected_preset_key: str | None = None
        self._previous_preset_key: str | None = None
        self._fit_combo: QComboBox | None = None
        self._motion_combo: QComboBox | None = None
        self._float_setters: dict[str, Callable[[float], None]] = {}
        self._color_setters: dict[str, Callable[[str], None]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        background_section = InspectorSection(
            "Background",
            subtitle="Reactive image treatment for the current background.",
        )
        self._enabled_toggle = StudioCheckBox("Background Image")
        self._enabled_toggle.toggled.connect(
            lambda checked: self._emit_patch({"backgroundEnabled": checked})
        )
        background_section.add_widget(self._enabled_toggle)

        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("Preset look")
        for value, label in BACKGROUND_STYLE_PRESETS:
            self._preset_combo.addItem(label, value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_index_changed)
        background_section.add_widget(form_row("Preset Look", self._preset_combo))

        restore_row = QHBoxLayout()
        restore_row.addStretch()
        restore_btn = QPushButton("Restore original")
        restore_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        restore_btn.setToolTip("Reset this preset look to factory defaults (keeps your video template Save separate).")
        restore_btn.clicked.connect(self.preset_restore_requested.emit)
        restore_row.addWidget(restore_btn)
        restore_host = QWidget()
        restore_host.setLayout(restore_row)
        background_section.add_widget(restore_host)
        background_section.add_widget(
            note_box(
                "Preset tweaks stay for this session only and reset when the app closes. "
                "Restore original clears only this preset look. Save still writes the current look to the video template."
            )
        )

        select_row = QHBoxLayout()
        select_row.addStretch()
        select_btn = QPushButton("Select Background")
        select_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        select_btn.clicked.connect(self.select_background_requested.emit)
        select_row.addWidget(select_btn)
        select_host = QWidget()
        select_host.setLayout(select_row)
        background_section.add_widget(select_host)
        background_section.add_widget(
            note_box(
                "Saved with the template for Video-page preview only. "
                "Music → Video automation always uses the AI-generated batch background, not this image."
            )
        )

        self._details_host = QWidget()
        details_layout = QVBoxLayout(self._details_host)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)

        self._fit_combo = QComboBox()
        for value, label in BACKGROUND_FIT_OPTIONS:
            self._fit_combo.addItem(label, value)
        self._fit_combo.currentIndexChanged.connect(self._on_fit_changed)
        details_layout.addWidget(form_row("Fit", self._fit_combo))

        details_layout.addWidget(
            self._add_float("backgroundUserScale", "Scale", 0.1, 4, 0.05, lambda v: f"{round(v * 100)}%")
        )

        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("Reset transform")
        reset_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        reset_btn.clicked.connect(self.reset_transform_requested.emit)
        reset_row.addWidget(reset_btn)
        reset_host = QWidget()
        reset_host.setLayout(reset_row)
        details_layout.addWidget(reset_host)

        for field, label, minimum, maximum, step in (
            ("backgroundBrightness", "Brightness", 0, 2, 0.01),
            ("backgroundContrast", "Contrast", 0, 2, 0.01),
            ("backgroundSaturation", "Saturation", 0, 2, 0.01),
            ("backgroundHue", "Hue", -180, 180, 1),
            ("backgroundReactivity", "Audio Reactivity", 0, 20, 0.05),
        ):
            details_layout.addWidget(self._add_float(field, label, minimum, maximum, step))

        details_layout.addWidget(
            self._add_float("backgroundSmoothing", "Reaction Smoothness", 0, 0.99, 0.01)
        )

        self._motion_combo = QComboBox()
        for value, label in BACKGROUND_MOTION_OPTIONS:
            self._motion_combo.addItem(label, value)
        self._motion_combo.currentIndexChanged.connect(self._on_motion_changed)
        details_layout.addWidget(form_row("Motion", self._motion_combo))

        for field, label, minimum, maximum, step in (
            ("backgroundMotionZoomStrength", "Zoom Strength", 0, 20, 0.05),
            ("backgroundMotionVibrateStrength", "Vibrate Strength", 0, 20, 0.05),
            ("backgroundMotionSpeed", "Motion Speed", 0, 20, 0.05),
        ):
            details_layout.addWidget(self._add_float(field, label, minimum, maximum, step))

        background_section.add_widget(self._details_host)
        root.addWidget(background_section)

        corner_section = InspectorSection(
            "Corner Effects",
            subtitle="Add subtle vignette or smoky corners for a more cinematic frame.",
        )
        corner_section.add_widget(
            self._add_toggle("vignetteEnabled", "Vignette", lambda checked: {"vignetteEnabled": checked})
        )
        for field, label in (
            ("vignetteStrength", "Vignette Strength"),
            ("vignetteFeather", "Vignette Feather"),
            ("vignetteOpacity", "Vignette Opacity"),
        ):
            corner_section.add_widget(self._add_float(field, label, 0, 1, 0.01))
        corner_section.add_widget(
            self._add_float("vignetteReactivity", "Vignette Audio React", 0, 5, 0.05)
        )
        corner_section.add_widget(self._add_color("vignetteColor", "Vignette Color"))
        corner_section.add_widget(
            note_box(
                "Vignette Audio React opens the dark corners on bass/kick and lightning strikes, "
                "so a bright background can flash through when bolts hit."
            )
        )

        corner_section.add_widget(
            self._add_toggle("smokeEnabled", "Smoke", lambda checked: {"smokeEnabled": checked})
        )
        for field, label in (
            ("smokeStrength", "Smoke Strength"),
            ("smokeBlur", "Smoke Blur"),
            ("smokeNoise", "Smoke Noise"),
            ("smokeOpacity", "Smoke Opacity"),
        ):
            corner_section.add_widget(self._add_float(field, label, 0, 1, 0.01))
        corner_section.add_widget(self._add_float("smokeSpeed", "Smoke Motion Speed", 0, 2, 0.01))
        corner_section.add_widget(self._add_color("smokeColor", "Smoke Color"))
        root.addWidget(corner_section)
        root.addStretch()

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
            on_change=lambda value, key=field: self._emit_patch({key: value}),
            format_value=format_value,
        )
        self._float_setters[field] = setter
        return widget

    def _add_color(self, field: str, label: str) -> QWidget:
        widget, setter = build_color_field(
            label,
            value="#000000",
            on_change=lambda value, key=field: self._emit_patch({key: value}),
            parent=self,
        )
        self._color_setters[field] = setter
        return widget

    def _add_toggle(self, field: str, label: str, patch_builder: Callable[[bool], dict]) -> QCheckBox:
        checkbox = StudioCheckBox(label)
        checkbox.toggled.connect(lambda checked: self._emit_patch(patch_builder(checked)))
        setattr(self, f"_{field}_toggle", checkbox)
        return checkbox

    def _on_fit_changed(self, _index: int) -> None:
        if self._binding or self._fit_combo is None:
            return
        value = self._fit_combo.currentData()
        if isinstance(value, str):
            self._emit_patch({"backgroundFitMode": value})

    def _on_motion_changed(self, _index: int) -> None:
        if self._binding or self._motion_combo is None:
            return
        value = self._motion_combo.currentData()
        if isinstance(value, str):
            self._emit_patch({"backgroundMotionMode": value})

    def _emit_patch(self, patch: dict) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(patch)

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        try:
            enabled = bool(draft.get("backgroundEnabled", True))
            if self._enabled_toggle is not None:
                self._enabled_toggle.setChecked(enabled)
            if self._details_host is not None:
                self._details_host.setVisible(enabled)

            if self._fit_combo is not None:
                index = self._fit_combo.findData(str(draft.get("backgroundFitMode") or "cover"))
                if index >= 0:
                    self._fit_combo.setCurrentIndex(index)
            if self._motion_combo is not None:
                index = self._motion_combo.findData(str(draft.get("backgroundMotionMode") or "none"))
                if index >= 0:
                    self._motion_combo.setCurrentIndex(index)

            for field, setter in self._float_setters.items():
                setter(float(draft.get(field, 0)))

            for field, setter in self._color_setters.items():
                setter(str(draft.get(field) or "#000000"))

            for field in ("vignetteEnabled", "smokeEnabled"):
                toggle = getattr(self, f"_{field}_toggle", None)
                if toggle is not None:
                    toggle.setChecked(bool(draft.get(field)))

            if self._preset_combo is not None:
                current = self._preset_combo.currentData()
                if isinstance(current, str) and current:
                    self._selected_preset_key = current
                    if self._previous_preset_key is None:
                        self._previous_preset_key = current
        finally:
            self._binding = False

    def mount_effect_pack_selector(self, selector: QWidget) -> None:
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(0, selector)
