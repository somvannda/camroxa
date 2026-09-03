"""Particles domain inspector — Phase 9b."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from features.create.widgets.studio_controls import StudioCheckBox

from features.video.lib.particle_settings import (
    PARTICLE_MOTION_PRESETS,
    PARTICLE_SPAWN_AREA_OPTIONS,
    PARTICLE_SPAWN_MODE_OPTIONS,
    PARTICLE_SPAWN_TRIGGER_OPTIONS,
    PARTICLE_STYLE_OPTIONS,
    PARTICLE_TRAVEL_MODE_OPTIONS,
)
from features.video.lib.particle_color_engine import apply_particle_color_draft_patch
from features.video.lib.particle_style_registry import resolve_active_particle_preset_key
from features.video.widgets.particle_color_editor import ParticleColorEditor
from features.video.widgets.inspector_fields import (
    InspectorSection,
    build_color_field,
    build_float_slider,
)
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID
from shared.widgets.settings_ui import form_row, note_box


class ParticlesInspector(QWidget):
    draft_patch_requested = Signal(dict)
    preset_apply_requested = Signal(str)
    preset_restore_requested = Signal()

    _MAIN_FLOATS: tuple[tuple[str, str, float, float, float], ...] = (
        ("particlesSpeed", "Move Speed", 0.5, 25, 0.25),
        ("particlesLifetimeSec", "Lifetime", 0.05, 10, 0.1),
        ("particlesSize", "Particle Size", 1, 20, 0.5),
        ("particlesOpacity", "Opacity", 0, 1, 0.05),
        ("particlesGlow", "Neon Glow", 0, 1, 0.05),
        ("particlesReactivity", "Audio Reactivity", 0, 1, 0.05),
        ("particlesReactStrength", "React Strength", 0, 1, 0.05),
    )

    _ADVANCED_FLOATS: tuple[tuple[str, str, float, float, float], ...] = (
        ("particlesMaxCount", "Max Count", 200, 2000, 25),
        ("particlesSpawnRate", "Birth Rate", 50, 1500, 25),
        ("particlesSpawnThreshold", "Spawn Threshold", 0, 1, 0.02),
        ("particlesSizeJitter", "Size Variance", 0, 1, 0.05),
        ("particlesDrift", "Drift", 0, 1, 0.05),
        ("particlesSwirl", "Swirl", 0, 1, 0.05),
        ("particlesTrailWidth", "Trail Width", 0.1, 1.0, 0.05),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._draft_snapshot: dict = {}
        self._preset_combo: QComboBox | None = None
        self._selected_preset_key: str | None = None
        self._previous_preset_key: str | None = None
        self._combo_fields: dict[str, QComboBox] = {}
        self._float_setters: dict[str, Callable[[float], None]] = {}
        self._color_setters: dict[str, Callable[[str], None]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        section = InspectorSection(
            "Particles",
            subtitle="Control density, motion, and visual behavior for the particle system.",
        )
        self._enabled_toggle = StudioCheckBox("Particles")
        self._enabled_toggle.toggled.connect(
            lambda checked: self._emit_patch({"particlesEnabled": checked})
        )
        section.add_widget(self._enabled_toggle)

        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("Preset look")
        for value, label in PARTICLE_MOTION_PRESETS:
            self._preset_combo.addItem(label, value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_index_changed)
        section.add_widget(form_row("Preset Look", self._preset_combo))

        restore_row = QHBoxLayout()
        restore_row.addStretch()
        restore_btn = QPushButton("Restore original")
        restore_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        restore_btn.setToolTip(
            "Reset the selected preset to factory defaults. Session tweaks reset when the app closes."
        )
        restore_btn.clicked.connect(self.preset_restore_requested.emit)
        restore_row.addWidget(restore_btn)
        restore_host = QWidget()
        restore_host.setLayout(restore_row)
        section.add_widget(restore_host)
        section.add_widget(
            note_box(
                "Presets apply a full particle recipe. Tweaks stay for this session only and reset when the app closes. "
                "Restore original resets only the selected preset look to factory. "
                "Save still writes the current look to this video template."
            )
        )

        section.add_widget(self._build_combo("particlesStyle", "Style", PARTICLE_STYLE_OPTIONS))
        section.add_widget(
            note_box(
                "Music Notes randomly picks neon note symbols. Raise Neon Glow to bloom dots and icons "
                "(works with Dot, Soft Glow, Bokeh, and Music Notes)."
            )
        )
        section.add_widget(self._build_combo("particlesSpawnArea", "Spawn Area", PARTICLE_SPAWN_AREA_OPTIONS))
        section.add_widget(self._build_combo("particlesTravelMode", "Travel Mode", PARTICLE_TRAVEL_MODE_OPTIONS))
        section.add_widget(self._build_combo("particlesSpawnMode", "Spawn Mode", PARTICLE_SPAWN_MODE_OPTIONS))

        self._trail_toggle = StudioCheckBox("Motion Trail")
        self._trail_toggle.setToolTip(
            "Draw fading position history behind each particle. Particles domain only."
        )
        self._trail_toggle.toggled.connect(
            lambda checked: self._emit_patch({"particlesTrailEnabled": checked})
        )
        section.add_widget(self._trail_toggle)

        for field, label, minimum, maximum, step in self._MAIN_FLOATS:
            section.add_widget(self._add_float(field, label, minimum, maximum, step))

        trail_len_widget, trail_len_setter = build_float_slider(
            "Trail Length",
            minimum=2,
            maximum=24,
            step=1,
            value=8,
            on_change=lambda value: self._emit_patch({"particlesTrailLength": int(round(value))}),
            format_value=lambda value: f"{int(round(value))}",
        )
        trail_len_widget.setToolTip("How many past positions to keep (2–24). Longer = longer streaks.")
        self._float_setters["particlesTrailLength"] = trail_len_setter
        section.add_widget(trail_len_widget)

        trail_fade_widget, trail_fade_setter = build_float_slider(
            "Trail Fade",
            minimum=0.05,
            maximum=0.98,
            step=0.05,
            value=0.65,
            on_change=lambda value: self._emit_patch({"particlesTrailFade": round(float(value), 2)}),
        )
        trail_fade_widget.setToolTip(
            "How quickly older trail segments dim. Lower = longer visible streak; higher = snappier fade."
        )
        self._float_setters["particlesTrailFade"] = trail_fade_setter
        section.add_widget(trail_fade_widget)

        self._color_editor = ParticleColorEditor(self)
        self._color_editor.color_patch_requested.connect(self._on_color_engine_patch)
        section.add_widget(self._color_editor)
        self._base_color_widget = self._add_color("particlesColor", "Base Color")
        self._react_color_widget = self._add_color("particlesReactColor", "React Color")
        section.add_widget(self._base_color_widget)
        section.add_widget(self._react_color_widget)
        # Higher = snappier color flash; lower = slower blend into React Color.
        # Stored as particlesSmoothing (Electron parity): speed = 1 - smoothing.
        flash_widget, flash_setter = build_float_slider(
            "React Flash Speed",
            minimum=0.01,
            maximum=1.0,
            step=0.05,
            value=0.35,
            on_change=self._on_react_flash_speed_changed,
            format_value=lambda value: f"{value:.2f}",
        )
        flash_widget.setToolTip(
            "How quickly particles blend into React Color on beats. "
            "Lower = slower / smoother. Higher = faster / snappier."
        )
        self._float_setters["particlesReactFlashSpeed"] = flash_setter
        section.add_widget(flash_widget)

        advanced = InspectorSection("Advanced")
        for field, label, minimum, maximum, step in self._ADVANCED_FLOATS:
            advanced.add_widget(self._add_float(field, label, minimum, maximum, step))
        advanced.add_widget(
            self._build_combo("particlesSpawnTrigger", "Spawn Trigger", PARTICLE_SPAWN_TRIGGER_OPTIONS)
        )
        section.add_widget(advanced)

        root.addWidget(section)
        root.addStretch()

    def _build_combo(
        self,
        field: str,
        label: str,
        options: tuple[tuple[str, str], ...],
    ) -> QWidget:
        combo = QComboBox()
        for value, option_label in options:
            combo.addItem(option_label, value)
        combo.currentIndexChanged.connect(lambda _index, key=field: self._on_combo_changed(key))
        self._combo_fields[field] = combo
        return form_row(label, combo)

    def _add_float(
        self,
        field: str,
        label: str,
        minimum: float,
        maximum: float,
        step: float,
    ) -> QWidget:
        widget, setter = build_float_slider(
            label,
            minimum=minimum,
            maximum=maximum,
            step=step,
            value=minimum,
            on_change=lambda value, key=field: self._emit_patch(
                {
                    key: int(value)
                    if key in {"particlesMaxCount", "particlesSpawnRate", "particlesTrailLength"}
                    else value
                }
            ),
        )
        self._float_setters[field] = setter
        return widget

    def _add_color(self, field: str, label: str) -> QWidget:
        widget, setter = build_color_field(
            label,
            value="#ffffff",
            on_change=lambda value, key=field: self._on_color_field_changed(key, value),
            parent=self,
        )
        self._color_setters[field] = setter
        return widget

    def _on_combo_changed(self, field: str) -> None:
        if self._binding:
            return
        combo = self._combo_fields.get(field)
        if combo is None:
            return
        value = combo.currentData()
        if isinstance(value, str):
            self._emit_patch({field: value})

    def _on_react_flash_speed_changed(self, speed: float) -> None:
        # Invert for storage: Electron particlesSmoothing is lag amount.
        smoothing = float(max(0.0, min(0.99, 1.0 - float(speed))))
        self._emit_patch({"particlesSmoothing": smoothing})

    @staticmethod
    def _flash_speed_from_smoothing(smoothing: float) -> float:
        return float(max(0.01, min(1.0, 1.0 - float(smoothing))))

    def _on_preset_index_changed(self, _index: int) -> None:
        if self._binding or self._preset_combo is None:
            return
        preset = self._preset_combo.currentData()
        if isinstance(preset, str) and preset:
            # Combo already moved; keep the prior selection for session capture.
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

    def _on_color_field_changed(self, field: str, value: str) -> None:
        if field == "particlesColor":
            # Emit only color keys so a stale draft snapshot cannot overwrite
            # other live particle fields during deferred inspector rebind.
            merged = apply_particle_color_draft_patch(
                self._draft_snapshot,
                {"solidColor": value},
            )
            self._emit_patch(
                {
                    "particlesColor": merged.get("particlesColor"),
                    "particlesColorMode": merged.get("particlesColorMode"),
                    "particlesPaletteColors": merged.get("particlesPaletteColors"),
                    "particlesReactColor": merged.get("particlesReactColor"),
                }
            )
            return
        if field == "particlesReactColor":
            merged = apply_particle_color_draft_patch(
                self._draft_snapshot,
                {"reactColor": value},
            )
            self._emit_patch({"particlesReactColor": merged.get("particlesReactColor")})
            return
        self._emit_patch({field: value})

    def _on_color_engine_patch(self, patch: dict) -> None:
        merged = apply_particle_color_draft_patch(self._draft_snapshot, patch)
        color_keys = (
            "particlesColor",
            "particlesColorMode",
            "particlesPaletteColors",
            "particlesReactColor",
        )
        self._emit_patch({key: merged[key] for key in color_keys if key in merged})

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

    def bind_draft(self, draft: dict) -> None:
        self._binding = True
        try:
            self._draft_snapshot = dict(draft)
            self._enabled_toggle.setChecked(bool(draft.get("particlesEnabled", True)))
            self._trail_toggle.setChecked(bool(draft.get("particlesTrailEnabled", False)))

            for field, combo in self._combo_fields.items():
                index = combo.findData(str(draft.get(field) or ""))
                if index >= 0:
                    combo.setCurrentIndex(index)

            for field, setter in self._float_setters.items():
                if field == "particlesReactFlashSpeed":
                    setter(self._flash_speed_from_smoothing(float(draft.get("particlesSmoothing", 0.65))))
                else:
                    setter(float(draft.get(field, 0)))

            for field, setter in self._color_setters.items():
                setter(str(draft.get(field) or "#ffffff"))

            if self._preset_combo is not None:
                active_preset = resolve_active_particle_preset_key(draft)
                if active_preset:
                    index = self._preset_combo.findData(active_preset)
                    if index >= 0:
                        self._preset_combo.setCurrentIndex(index)
                # Keep the currently selected pack/custom entry when no built-in
                # preset matches exactly (user tweaked values). Do not force index 0.
                current = self._preset_combo.currentData()
                if isinstance(current, str) and current:
                    self._selected_preset_key = current
                    if self._previous_preset_key is None:
                        self._previous_preset_key = current

            self._color_editor.bind_draft(draft)
            color_mode = str(draft.get("particlesColorMode") or "solid")
            self._base_color_widget.setVisible(True)
            self._react_color_widget.setVisible(True)
            if hasattr(self._react_color_widget, "setToolTip"):
                tip = (
                    "Beat-reactive flash color mixed over each palette color."
                    if color_mode == "palette"
                    else "Beat-reactive flash color mixed over the base color."
                )
                self._react_color_widget.setToolTip(tip)
        finally:
            self._binding = False

    def _emit_patch(self, patch: dict) -> None:
        if self._binding:
            return
        self.draft_patch_requested.emit(patch)

    def mount_effect_pack_selector(self, selector: QWidget) -> None:
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(0, selector)
