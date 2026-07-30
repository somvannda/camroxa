"""Particle color engine section — solid base color + optional multi-color palette."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from features.video.lib.particle_color_engine import (
    PARTICLE_COLOR_MODE_OPTIONS,
    PARTICLE_PALETTE_PRESET_OPTIONS,
    apply_particle_color_draft_patch,
    build_particle_palette_preset_value,
    extract_particle_color_model,
    normalize_particle_palette_colors,
)
from features.video.lib.spectrum_color_engine import MAX_GRADIENT_COLOR_STOPS
from features.video.widgets.inspector_fields import build_color_field
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID
from shared.widgets.settings_ui import form_row


class ParticleColorEditor(QWidget):
    color_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._color_model: dict[str, Any] = {}
        self._gradient_stop_setters: list[Callable[[str], None]] = []
        self._palette_host: QWidget | None = None
        self._palette_stops_layout: QVBoxLayout | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mode_combo = QComboBox()
        for value, label in PARTICLE_COLOR_MODE_OPTIONS:
            self._mode_combo.addItem(label, value)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(form_row("Color Engine", self._mode_combo))

        self._palette_host = QWidget()
        palette_layout = QVBoxLayout(self._palette_host)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.setSpacing(6)

        self._palette_preset_combo = QComboBox()
        self._palette_preset_combo.setToolTip("Palette Preset")
        for value, label in PARTICLE_PALETTE_PRESET_OPTIONS:
            self._palette_preset_combo.addItem(label, value)
        self._palette_preset_combo.currentIndexChanged.connect(self._on_palette_preset_changed)
        palette_layout.addWidget(self._palette_preset_combo)

        stop_actions = QHBoxLayout()
        stop_actions.setContentsMargins(0, 0, 0, 0)
        stop_actions.setSpacing(6)
        add_stop = QPushButton("Add Stop")
        add_stop.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        add_stop.clicked.connect(self._add_palette_stop)
        remove_stop = QPushButton("Remove Stop")
        remove_stop.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        remove_stop.clicked.connect(self._remove_palette_stop)
        stop_actions.addWidget(add_stop)
        stop_actions.addWidget(remove_stop)
        stop_actions.addStretch()
        palette_layout.addLayout(stop_actions)

        palette_layout.addWidget(QLabel("Palette Stops"))
        self._palette_stops_host = QWidget()
        self._palette_stops_layout = QVBoxLayout(self._palette_stops_host)
        self._palette_stops_layout.setContentsMargins(0, 0, 0, 0)
        self._palette_stops_layout.setSpacing(6)
        palette_layout.addWidget(self._palette_stops_host)
        self._react_note = QLabel("React Color below flashes over palette colors on beats.")
        self._react_note.setWordWrap(True)
        palette_layout.addWidget(self._react_note)
        layout.addWidget(self._palette_host)
        self._palette_host.hide()

    def _emit_patch(self, patch: dict[str, Any]) -> None:
        if self._binding:
            return
        mode = str(self._color_model.get("mode") or "solid")
        if mode == "palette" and patch.get("mode") is None and "paletteColors" in patch:
            patch = {**patch, "mode": "palette"}
        self.color_patch_requested.emit(patch)

    def _on_mode_changed(self, _index: int) -> None:
        mode = self._mode_combo.currentData()
        if mode == "palette":
            colors = normalize_particle_palette_colors(
                list(self._color_model.get("paletteColors") or []),
                str(self._color_model.get("solidColor") or "#ffffff"),
                require_stops=True,
            )
            self._emit_patch({"mode": "palette", "paletteColors": colors})
        else:
            self._emit_patch({"mode": "solid"})

    def _on_palette_preset_changed(self, _index: int) -> None:
        raw = self._palette_preset_combo.currentData()
        if not isinstance(raw, str) or not raw:
            return
        colors = [part.strip() for part in raw.split(",") if part.strip()]
        solid = str(self._color_model.get("solidColor") or "#ffffff")
        self._emit_patch({"paletteColors": normalize_particle_palette_colors(colors, solid, require_stops=True)})

    def _add_palette_stop(self) -> None:
        colors = list(self._color_model.get("paletteColors") or [])
        if len(colors) >= MAX_GRADIENT_COLOR_STOPS:
            return
        colors.append(colors[-1] if colors else str(self._color_model.get("solidColor") or "#ffffff"))
        self._emit_patch(
            {
                "paletteColors": normalize_particle_palette_colors(
                    colors,
                    str(self._color_model.get("solidColor") or "#ffffff"),
                    require_stops=True,
                )
            }
        )

    def _remove_palette_stop(self) -> None:
        colors = list(self._color_model.get("paletteColors") or [])
        if len(colors) <= 2:
            return
        self._emit_patch(
            {
                "paletteColors": normalize_particle_palette_colors(
                    colors[:-1],
                    str(self._color_model.get("solidColor") or "#ffffff"),
                    require_stops=True,
                )
            }
        )

    def _patch_palette_stop(self, stop_index: int, value: str) -> None:
        colors = list(self._color_model.get("paletteColors") or [])
        if stop_index >= len(colors):
            return
        colors[stop_index] = value
        self._emit_patch({"paletteColors": colors})

    def _rebuild_palette_stops(self, colors: list[str]) -> None:
        if self._palette_stops_layout is None:
            return
        while self._palette_stops_layout.count():
            item = self._palette_stops_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._gradient_stop_setters.clear()
        for index, color in enumerate(colors):
            widget, setter = build_color_field(
                f"Stop {index + 1}",
                value=color,
                on_change=lambda value, stop_index=index: self._patch_palette_stop(stop_index, value),
                parent=self,
            )
            self._gradient_stop_setters.append(setter)
            self._palette_stops_layout.addWidget(widget)

    def bind_draft(self, draft: dict[str, Any]) -> None:
        self._binding = True
        try:
            self._color_model = extract_particle_color_model(
                {
                    "color": draft.get("particlesColor"),
                    "colorMode": draft.get("particlesColorMode"),
                    "paletteColors": draft.get("particlesPaletteColors"),
                    "reactColor": draft.get("particlesReactColor"),
                }
            )
            mode = str(self._color_model.get("mode") or "solid")
            mode_index = self._mode_combo.findData(mode)
            if mode_index >= 0:
                self._mode_combo.setCurrentIndex(mode_index)
            if self._palette_host is not None:
                self._palette_host.setVisible(mode == "palette")
            if hasattr(self, "_react_note"):
                self._react_note.setVisible(mode == "palette")

            palette_colors = list(self._color_model.get("paletteColors") or [])
            preset_value = build_particle_palette_preset_value(palette_colors)
            preset_index = self._palette_preset_combo.findData(preset_value)
            self._palette_preset_combo.blockSignals(True)
            if preset_index >= 0:
                self._palette_preset_combo.setCurrentIndex(preset_index)
            else:
                self._palette_preset_combo.setCurrentIndex(-1)
            self._palette_preset_combo.blockSignals(False)
            self._rebuild_palette_stops(palette_colors)
        finally:
            self._binding = False

    @staticmethod
    def merge_draft_patch(draft: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        return apply_particle_color_draft_patch(draft, patch)
