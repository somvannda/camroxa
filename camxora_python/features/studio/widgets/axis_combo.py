"""Shared catalog helpers for Studio axes."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from features.studio.widgets.scroll_catalog_picker import ScrollCatalogPicker


def populate_combo(
    combo: QComboBox,
    options: tuple[tuple[str, str], ...],
    *,
    include_none: bool = True,
    none_label: str = "None",
) -> None:
    combo.clear()
    if include_none:
        combo.addItem(none_label, "none")
    for value, label in options:
        combo.addItem(label, value)


def set_combo_data(combo: QComboBox, value: str | None, *, fallback: str = "none") -> None:
    target = str(value or fallback)
    idx = combo.findData(target)
    if idx < 0:
        idx = combo.findData(fallback)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def populate_picker(
    picker: ScrollCatalogPicker,
    options: tuple[tuple[str, str], ...],
    *,
    include_none: bool = True,
    none_label: str = "None",
) -> None:
    """Expert-only catalog strips (horizontal scroll chips)."""
    picker.set_options(options, include_none=include_none, none_label=none_label)


def set_picker_data(
    picker: ScrollCatalogPicker, value: str | None, *, fallback: str = "none"
) -> None:
    picker.set_value(value, fallback=fallback)
