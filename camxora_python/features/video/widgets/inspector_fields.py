"""Reusable video inspector field rows — standard theme only."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_controls import StudioCheckBox

from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel, form_row


class InspectorSection(SettingsPanel):
    """Nested account_card section inside a domain inspector."""

    def __init__(self, title: str, *, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, subtitle=subtitle, fill_available_height=False, parent=parent)


def slider_row(
    label: str,
    *,
    minimum: int,
    maximum: int,
    value: int,
    on_change: Callable[[int], None],
) -> QWidget:
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    value_label = QLabel(f"{label} ({value})")
    value_label.setObjectName(SUBTITLE_LABEL_ID)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(minimum)
    slider.setMaximum(maximum)
    slider.setValue(value)

    def _emit(raw: int) -> None:
        value_label.setText(f"{label} ({raw})")
        on_change(raw)

    slider.valueChanged.connect(_emit)
    layout.addWidget(value_label)
    layout.addWidget(slider)
    return host


def toggle_row(label: str, *, checked: bool, on_change: Callable[[bool], None]) -> QWidget:
    checkbox = StudioCheckBox(label)
    checkbox.setChecked(checked)
    checkbox.toggled.connect(on_change)
    return checkbox


def combo_row(
    label: str,
    options: tuple[tuple[str, str], ...],
    *,
    value: str,
    on_change: Callable[[str], None],
) -> QWidget:
    combo = QComboBox()
    for option_value, option_label in options:
        combo.addItem(option_label, option_value)
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)

    def _emit(_index: int) -> None:
        data = combo.currentData()
        if isinstance(data, str):
            on_change(data)

    combo.currentIndexChanged.connect(_emit)
    return form_row(label, combo)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def build_float_slider(
    label: str,
    *,
    minimum: float,
    maximum: float,
    step: float,
    value: float,
    on_change: Callable[[float], None],
    format_value: Callable[[float], str] | None = None,
) -> tuple[QWidget, Callable[[float], None]]:
    safe_step = step if step > 0 else 1.0
    step_count = max(1, round((maximum - minimum) / safe_step))
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    def _format(raw_value: float) -> str:
        if format_value is not None:
            return format_value(raw_value)
        if safe_step < 1:
            return f"{raw_value:.2f}"
        if abs(raw_value - round(raw_value)) < 0.001:
            return str(int(round(raw_value)))
        return f"{raw_value:.2f}"

    clamped = _clamp(value, minimum, maximum)
    value_label = QLabel(f"{label} ({_format(clamped)})")
    value_label.setObjectName(SUBTITLE_LABEL_ID)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(step_count)

    def _to_slider(raw_value: float) -> int:
        return round((_clamp(raw_value, minimum, maximum) - minimum) / safe_step)

    def _from_slider(raw: int) -> float:
        snapped = minimum + raw * safe_step
        return round(snapped, max(0, len(str(safe_step).split(".")[-1]) if safe_step < 1 else 0))

    slider.setValue(_to_slider(clamped))

    def _emit(raw: int) -> None:
        next_value = _from_slider(raw)
        value_label.setText(f"{label} ({_format(next_value)})")
        on_change(next_value)

    slider.valueChanged.connect(_emit)
    layout.addWidget(value_label)
    layout.addWidget(slider)

    def set_value(next_value: float) -> None:
        slider.blockSignals(True)
        slider.setValue(_to_slider(next_value))
        value_label.setText(f"{label} ({_format(_from_slider(slider.value()))})")
        slider.blockSignals(False)

    return host, set_value


def build_color_field(
    label: str,
    *,
    value: str,
    on_change: Callable[[str], None],
    parent: QWidget | None = None,
    show_label: bool = True,
) -> tuple[QWidget, Callable[[str], None]]:
    # Match the QCheckBox indicator: 14px square with 3px rounded corners.
    swatch = QPushButton()
    swatch.setFixedSize(14, 14)

    def _apply_color(hex_color: str) -> None:
        normalized = hex_color if hex_color.startswith("#") else f"#{hex_color}"
        swatch.setStyleSheet(
            f"background-color: {normalized};"
            " border: 1px solid rgba(255,255,255,0.25);"
            " border-radius: 3px;"
            " padding: 0; min-height: 0; min-width: 0;"
        )
        swatch.setText("")

    def _pick_color() -> None:
        current = QColor(str(value or "#000000"))
        chosen = QColorDialog.getColor(current, parent, f"Choose {label}")
        if chosen.isValid():
            on_change(chosen.name())

    _apply_color(str(value or "#000000"))
    swatch.clicked.connect(_pick_color)

    def set_value(next_value: str) -> None:
        nonlocal value
        value = next_value
        _apply_color(next_value)

    if show_label:
        return form_row(label, swatch), set_value
    return swatch, set_value
