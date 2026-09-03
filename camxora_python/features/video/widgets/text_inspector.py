"""Text and animation inspector panels — port of TextInspectorPanel."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_controls import StudioCheckBox

from features.video.lib.spectrum_style_registry import ANCHOR_OPTIONS
from features.video.lib.text_editor import get_text_anchor_alignment
from features.video.lib.text_settings import TEXT_ANIMATION_OPTIONS
from features.video.widgets.inspector_fields import (
    InspectorSection,
    build_color_field,
    build_float_slider,
)
from features.video.widgets.text_layer_list import TextLayerListPanel
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row, note_box


class TextInspectorPanel(QWidget):
    overlay_patch_requested = Signal(dict)
    text_case_requested = Signal(str)
    anchor_alignment_requested = Signal(str)
    style_preset_requested = Signal(str)

    _STYLE_PRESETS: tuple[tuple[str, str], ...] = (
        ("neon_outline", "Aa"),
        ("soft_glow", "Aa"),
        ("dark_stroke", "Aa"),
        ("lower_third_title", "Aa"),
        ("kinetic_shout", "Aa"),
        ("neon_brush_stack", "FX"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._overlay: dict | None = None
        self._mode_tabs: QTabWidget | None = None
        self._text_edit: QTextEdit | None = None
        self._float_setters: dict[str, Callable[[float], None]] = {}
        self._color_setters: dict[str, Callable[[str], None]] = {}
        self._alignment_buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._empty_state = QFrame()
        self._empty_state.setObjectName("account_card")
        empty_layout = QVBoxLayout(self._empty_state)
        empty_layout.addWidget(QLabel("Text Inspector"))
        empty_layout.addWidget(
            note_box(
                "No text layer is selected yet. Select a layer from the list above, "
                "or add one with Add or Presets."
            )
        )
        root.addWidget(self._empty_state)

        self._editor_host = QWidget()
        editor_layout = QVBoxLayout(self._editor_host)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(8)

        self._mode_tabs = QTabWidget()
        self._mode_tabs.addTab(self._build_basic_tab(), "Basic")
        self._mode_tabs.addTab(self._build_style_tab(), "Style")
        self._mode_tabs.addTab(self._build_effects_tab(), "Effects")
        editor_layout.addWidget(self._mode_tabs)
        root.addWidget(self._editor_host)
        self._editor_host.hide()

    def _build_basic_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Default text")
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(QLabel("Default text"))
        layout.addWidget(self._text_edit)

        layout.addWidget(self._add_float("fontSize", "Font Size", 8, 320, 1))

        case_row = QHBoxLayout()
        case_row.setContentsMargins(0, 0, 0, 0)
        for mode, label in (("upper", "TT"), ("lower", "tt"), ("title", "Tt")):
            button = QPushButton(label)
            button.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
            button.clicked.connect(lambda _checked=False, key=mode: self.text_case_requested.emit(key))
            case_row.addWidget(button)
        case_host = QWidget()
        case_host.setLayout(case_row)
        layout.addWidget(QLabel("Case"))
        layout.addWidget(case_host)

        layout.addWidget(self._add_color("color", "Color"))

        layout.addWidget(QLabel("Alignment"))
        align_row = QHBoxLayout()
        align_row.setContentsMargins(0, 0, 0, 0)
        for alignment in ("left", "center", "right"):
            button = QPushButton(alignment.title())
            button.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
            button.clicked.connect(
                lambda _checked=False, key=alignment: self.anchor_alignment_requested.emit(key)
            )
            self._alignment_buttons[alignment] = button
            align_row.addWidget(button)
        align_host = QWidget()
        align_host.setLayout(align_row)
        layout.addWidget(align_host)
        layout.addStretch()
        return page

    def _build_style_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._add_color("color", "Fill"))
        layout.addWidget(self._add_color("strokeColor", "Stroke"))
        layout.addWidget(self._add_float("strokeWidth", "Stroke Width", 0, 12, 0.1))

        layout.addWidget(QLabel("Preset style"))
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        for preset_id, label in self._STYLE_PRESETS:
            button = QPushButton(label)
            button.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
            button.clicked.connect(
                lambda _checked=False, key=preset_id: self.style_preset_requested.emit(key)
            )
            preset_row.addWidget(button)
        preset_host = QWidget()
        preset_host.setLayout(preset_row)
        layout.addWidget(preset_host)
        layout.addStretch()
        return page

    def _build_effects_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self._add_float("shadow", "Shadow", 0, 1, 0.01))
        layout.addWidget(
            self._add_float(
                "fontSizeScale",
                "Scale",
                20,
                400,
                1,
                format_value=lambda value: f"{int(value)}%",
                patch_field="fontSize",
                patch_transform=lambda percent, overlay: max(
                    8.0, (46.0 * percent) / 100.0
                ),
            )
        )
        layout.addWidget(self._add_float("x", "X", -1000, 1000, 1))
        layout.addWidget(self._add_float("y", "Y", -1000, 1000, 1))
        layout.addStretch()
        return page

    def _add_float(
        self,
        field: str,
        label: str,
        minimum: float,
        maximum: float,
        step: float,
        *,
        format_value: Callable[[float], str] | None = None,
        patch_field: str | None = None,
        patch_transform: Callable[[float, dict], float] | None = None,
    ) -> QWidget:
        def _emit(value: float) -> None:
            if patch_transform is not None and self._overlay is not None:
                self.overlay_patch_requested.emit(
                    {patch_field or field: patch_transform(value, self._overlay)}
                )
            else:
                key = patch_field or field
                payload: dict = {key: int(value) if key in {"x", "y", "fontSize"} else value}
                self.overlay_patch_requested.emit(payload)

        widget, setter = build_float_slider(
            label,
            minimum=minimum,
            maximum=maximum,
            step=step,
            value=minimum,
            on_change=_emit,
            format_value=format_value,
        )
        self._float_setters[field] = setter
        return widget

    def _add_color(self, field: str, label: str) -> QWidget:
        widget, setter = build_color_field(
            label,
            value="#ffffff",
            on_change=lambda value, key=field: self.overlay_patch_requested.emit({key: value}),
            parent=self,
        )
        self._color_setters[field] = setter
        return widget

    def _on_text_changed(self) -> None:
        if self._binding or self._text_edit is None:
            return
        self.overlay_patch_requested.emit({"text": self._text_edit.toPlainText()})

    def bind_overlay(self, overlay: dict | None) -> None:
        self._binding = True
        try:
            self._overlay = overlay
            has_overlay = overlay is not None
            self._empty_state.setVisible(not has_overlay)
            self._editor_host.setVisible(has_overlay)
            if not overlay:
                return

            if self._text_edit is not None:
                self._text_edit.setPlainText(str(overlay.get("text") or ""))

            if "fontSize" in self._float_setters:
                self._float_setters["fontSize"](float(overlay.get("fontSize") or 46))
            if "strokeWidth" in self._float_setters:
                self._float_setters["strokeWidth"](float(overlay.get("strokeWidth") or 0))
            if "shadow" in self._float_setters:
                self._float_setters["shadow"](float(overlay.get("shadow") or 0))
            if "x" in self._float_setters:
                self._float_setters["x"](float(overlay.get("x") or 0))
            if "y" in self._float_setters:
                self._float_setters["y"](float(overlay.get("y") or 0))
            if "fontSizeScale" in self._float_setters:
                font_size = float(overlay.get("fontSize") or 46)
                self._float_setters["fontSizeScale"](max(20, min(400, round((font_size / 46) * 100))))

            for field, setter in self._color_setters.items():
                setter(str(overlay.get(field) or "#ffffff"))

            active_alignment = get_text_anchor_alignment(str(overlay.get("anchor") or "center"))
            for alignment, button in self._alignment_buttons.items():
                button.setStyleSheet(
                    "font-weight: 700;" if alignment == active_alignment else ""
                )
        finally:
            self._binding = False


class TextAnimationPanel(QWidget):
    overlay_patch_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._binding = False
        self._enabled_toggle: QCheckBox | None = None
        self._animation_combo: QComboBox | None = None
        self._anchor_combo: QComboBox | None = None
        self._float_setters: dict[str, Callable[[float], None]] = {}
        self._position_x_slider: QSlider | None = None
        self._position_y_slider: QSlider | None = None
        self._position_x_label: QLabel | None = None
        self._position_y_label: QLabel | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self._empty_state = note_box("Select a text layer to edit animation timing and motion.")
        root.addWidget(self._empty_state)

        self._editor_host = QWidget()
        layout = QVBoxLayout(self._editor_host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        section = InspectorSection("Animation")
        self._enabled_toggle = StudioCheckBox("Enable")
        self._enabled_toggle.toggled.connect(
            lambda checked: self.overlay_patch_requested.emit({"enabled": checked})
        )
        section.add_widget(self._enabled_toggle)

        self._animation_combo = QComboBox()
        for value, label in TEXT_ANIMATION_OPTIONS:
            self._animation_combo.addItem(label, value)
        self._animation_combo.currentIndexChanged.connect(self._on_animation_changed)
        section.add_widget(form_row("Preset", self._animation_combo))

        section.add_widget(self._add_float("startSec", "Start (sec)", 0, 36000, 1))
        section.add_widget(self._add_float("durationSec", "Duration", 1, 36000, 1))

        self._anchor_combo = QComboBox()
        for value, label in ANCHOR_OPTIONS:
            self._anchor_combo.addItem(label, value)
        self._anchor_combo.currentIndexChanged.connect(self._on_anchor_changed)
        section.add_widget(form_row("Anchor", self._anchor_combo))

        self._position_x_label, self._position_x_slider = self._build_position_slider("X Offset")
        self._position_y_label, self._position_y_slider = self._build_position_slider("Y Offset")
        self._position_x_slider.valueChanged.connect(
            lambda value: self.overlay_patch_requested.emit({"x": float(value)})
        )
        self._position_y_slider.valueChanged.connect(
            lambda value: self.overlay_patch_requested.emit({"y": float(value)})
        )
        section.add_widget(self._position_slider_host(self._position_x_label, self._position_x_slider))
        section.add_widget(self._position_slider_host(self._position_y_label, self._position_y_slider))
        section.add_widget(self._add_float("shadow", "Shadow", 0, 1, 0.01))

        layout.addWidget(section)
        root.addWidget(self._editor_host)
        self._editor_host.hide()

    def _add_float(self, field: str, label: str, minimum: float, maximum: float, step: float) -> QWidget:
        widget, setter = build_float_slider(
            label,
            minimum=minimum,
            maximum=maximum,
            step=step,
            value=minimum,
            on_change=lambda value, key=field: self.overlay_patch_requested.emit({key: value}),
        )
        self._float_setters[field] = setter
        return widget

    @staticmethod
    def _build_position_slider(title: str) -> tuple[QLabel, QSlider]:
        label = QLabel(f"{title} (0)")
        label.setObjectName(SUBTITLE_LABEL_ID)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(-1000)
        slider.setMaximum(1000)
        slider.valueChanged.connect(lambda value: label.setText(f"{title} ({value})"))
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

    def _on_animation_changed(self, _index: int) -> None:
        if self._binding or self._animation_combo is None:
            return
        value = self._animation_combo.currentData()
        if isinstance(value, str):
            self.overlay_patch_requested.emit({"animation": value})

    def _on_anchor_changed(self, _index: int) -> None:
        if self._binding or self._anchor_combo is None:
            return
        value = self._anchor_combo.currentData()
        if isinstance(value, str):
            self.overlay_patch_requested.emit({"anchor": value})

    def bind_overlay(self, overlay: dict | None) -> None:
        self._binding = True
        try:
            has_overlay = overlay is not None
            self._empty_state.setVisible(not has_overlay)
            self._editor_host.setVisible(has_overlay)
            if not overlay:
                return

            if self._enabled_toggle is not None:
                self._enabled_toggle.setChecked(bool(overlay.get("enabled")))

            if self._animation_combo is not None:
                index = self._animation_combo.findData(str(overlay.get("animation") or "fade"))
                if index >= 0:
                    self._animation_combo.setCurrentIndex(index)

            if self._anchor_combo is not None:
                index = self._anchor_combo.findData(str(overlay.get("anchor") or "center"))
                if index >= 0:
                    self._anchor_combo.setCurrentIndex(index)

            for field, setter in self._float_setters.items():
                setter(float(overlay.get(field) or 0))

            position_x = int(round(float(overlay.get("x") or 0)))
            position_y = int(round(float(overlay.get("y") or 0)))
            if self._position_x_slider is not None:
                self._position_x_slider.setValue(position_x)
            if self._position_y_slider is not None:
                self._position_y_slider.setValue(position_y)
        finally:
            self._binding = False


class TextWorkspaceTab(QWidget):
    """Text tab — layer list plus Basic/Style/Effects inspector."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.layer_list = TextLayerListPanel()
        self.inspector = TextInspectorPanel()
        layout.addWidget(self.layer_list)
        layout.addWidget(self.inspector, stretch=1)
