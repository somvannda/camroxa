"""Module-level widget-factory utility functions.

Extracted from MainWindow to allow independent testing and reuse without
instantiating the full application window. Pure-computation helpers
(``split_metric_text``, ``format_music_updated_at``) require no Qt context
and are callable without a ``QApplication`` instance.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import style_helper
from ...app.widgets import AppDateEdit


# ---------------------------------------------------------------------------
# Pure-computation helpers (no QApplication required)
# ---------------------------------------------------------------------------


def split_metric_text(text: str) -> tuple[str, str]:
    """Split a metric string like ``'Title (value)'`` into ``(title, value)``.

    Returns ``(text, "")`` when no parenthesised suffix is found.
    """
    s = str(text or "").strip()
    if s.endswith(")") and " (" in s:
        idx = s.rfind(" (")
        if idx > 0:
            return s[:idx].strip(), s[idx + 2 : -1].strip()
    return s, ""


def format_music_updated_at(value: str) -> str:
    """Normalise a timestamp string to ``YYYY-MM-DDTHH:MM:SS`` (max 19 chars).

    Returns ``"-"`` for empty or whitespace-only input.
    """
    raw = str(value or "").strip()
    if not raw:
        return "-"
    normalized = raw.replace(" ", "T")
    if "+" in normalized:
        normalized = normalized.split("+", 1)[0]
    if normalized.endswith("Z"):
        normalized = normalized[:-1]
    return normalized[:19]


# ---------------------------------------------------------------------------
# Widget-construction helpers (require a running QApplication)
# ---------------------------------------------------------------------------


def set_metric_text(metric_value_label: QLabel, text: str) -> None:
    """Update a metric header's title and value labels from *text*."""
    title, value = split_metric_text(text)
    title_label = getattr(metric_value_label, "_metric_title_label", None)
    if isinstance(title_label, QLabel):
        title_label.setText(title)
    metric_value_label.setText(value)


def create_metric_header(
    initial_text: str, tokens: dict[str, str]
) -> tuple[QHBoxLayout, QLabel]:
    """Create a horizontal layout with a title label and a value label.

    Returns the layout and the value label (for later updates).
    """
    title, value = split_metric_text(initial_text)
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    title_label = QLabel(title)
    style_helper.set_label_role(title_label, "metricTitle")
    row.addWidget(title_label)
    row.addStretch(1)
    value_label = QLabel(value)
    style_helper.set_label_role(value_label, "metricValue")
    setattr(value_label, "_metric_title_label", title_label)
    row.addWidget(value_label)
    return row, value_label


def add_slider_row(
    layout: QVBoxLayout,
    initial_text: str,
    minimum: int,
    maximum: int,
    value: int,
    on_change: Callable[[int], None],
    tokens: dict[str, str],
    *,
    single_step: int = 1,
    page_step: int | None = None,
    tick_interval: int | None = None,
) -> tuple[QLabel, QSlider]:
    """Add a labelled slider row to *layout* and return (value_label, slider)."""
    header_row, value_label = create_metric_header(initial_text, tokens)
    layout.addLayout(header_row)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(int(minimum))
    slider.setMaximum(int(maximum))
    slider.setValue(int(value))
    slider.setSingleStep(int(single_step))
    if page_step is not None:
        slider.setPageStep(int(page_step))
    if tick_interval is not None:
        slider.setTickInterval(int(tick_interval))
    slider.valueChanged.connect(lambda v: on_change(v))
    layout.addWidget(slider)
    return value_label, slider


def configure_step_slider(
    slider: QSlider,
    event_target: QWidget,
    *,
    minimum_width: int | None = None,
    single_step: int = 1,
    page_step: int = 5,
    wheel_step: int = 2,
) -> QSlider:
    """Configure a slider with step sizes, focus policy, and event filter.

    *event_target* is installed as the event filter for the slider (typically
    the ``MainWindow`` instance that implements ``eventFilter``).
    """
    slider.setSingleStep(max(1, int(single_step)))
    slider.setPageStep(max(1, int(page_step)))
    slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    slider.setProperty("_wheelStep", max(1, int(wheel_step)))
    slider.installEventFilter(event_target)
    if minimum_width is not None:
        slider.setMinimumWidth(int(minimum_width))
    slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return slider


def _sync_toggle_button(toggle: QPushButton, checked: bool) -> None:
    """Set the toggle button text to reflect the checked state."""
    toggle.setText("ON" if checked else "OFF")


def add_toggle_row(
    layout: QVBoxLayout,
    label_text: str,
    on_change: Callable[[], None],
    tokens: dict[str, str],
) -> QPushButton:
    """Add a labelled toggle button row to *layout* and return the toggle."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    lab = QLabel(label_text)
    style_helper.set_label_role(lab, "subheading")
    row.addWidget(lab)
    row.addStretch()
    toggle = QPushButton("")
    toggle.setCheckable(True)
    toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    style_helper.set_button_role(toggle, "toggle")
    toggle.toggled.connect(lambda checked, btn=toggle: _sync_toggle_button(btn, checked))
    toggle.toggled.connect(lambda _: on_change())
    _sync_toggle_button(toggle, False)
    row.addWidget(toggle)
    layout.addLayout(row)
    return toggle


def add_form_row(
    layout: QVBoxLayout,
    label_text: str,
    field: QWidget,
    tokens: dict[str, str],
    *,
    apply_card_field: bool = False,
    label_min_width: int = 80,
) -> QLabel:
    """Add a labelled form row to *layout* and return the label widget."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    label = QLabel(label_text)
    style_helper.set_label_role(label, "metricTitle")
    label.setMinimumWidth(label_min_width)
    row.addWidget(label)
    if apply_card_field:
        style_helper.apply_card_field(field)
    row.addWidget(field, 1)
    layout.addLayout(row)
    return label


def make_panel_section(
    title_text: str,
    tokens: dict[str, str],
    *,
    subtitle_text: str = "",
    soft: bool = False,
) -> tuple[QWidget, QVBoxLayout]:
    """Create a styled panel section widget with a title and a body layout.

    Returns ``(box_widget, body_layout)`` where *body_layout* is where child
    content should be added.
    """
    box = QWidget()
    style_helper.set_panel_role(box, "softSection" if soft else "section")
    outer = QVBoxLayout(box)
    outer.setContentsMargins(
        9 if soft else 10,
        7 if soft else 8,
        9 if soft else 10,
        7 if soft else 8,
    )
    outer.setSpacing(4 if soft else 5)
    title_lab = QLabel(title_text)
    style_helper.set_label_role(title_lab, "compactTitle" if soft else "sectionTitle")
    outer.addWidget(title_lab)
    if subtitle_text:
        subtitle_lab = QLabel(subtitle_text)
        subtitle_lab.setWordWrap(True)
        style_helper.set_label_role(subtitle_lab, "compactSubtitle")
        outer.addWidget(subtitle_lab)
    body = QVBoxLayout()
    body.setContentsMargins(0, 1, 0, 0)
    body.setSpacing(4 if soft else 5)
    outer.addLayout(body)
    return box, body


def create_calendar_picker(
    on_change: Callable[[], None],
    tokens: dict[str, str],
    *,
    width: int = 108,
) -> QDateEdit:
    """Create a styled date-edit widget with a calendar popup.

    Returns the ``QDateEdit`` (actually an ``AppDateEdit``) configured with
    the standard format and minimum date.
    """
    picker = AppDateEdit()
    picker.setCalendarPopup(True)
    picker.setDisplayFormat("MM/dd/yyyy")
    picker.setMinimumDate(QDate(2000, 1, 1))
    picker.setSpecialValueText("MM/DD/YYYY")
    picker.setDate(picker.minimumDate())
    picker.setFixedWidth(max(int(width), 118))
    style_helper.apply_card_field(picker)
    picker.dateChanged.connect(lambda _date: on_change())
    return picker


def calendar_picker_value(picker: QDateEdit | None) -> str:
    """Return the current date value of *picker* as ``'yyyy-MM-dd'``, or ``""``."""
    if picker is None:
        return ""
    current = picker.date()
    return current.toString("yyyy-MM-dd")


def set_calendar_picker_value(picker: QDateEdit | None, value: str) -> None:
    """Set *picker*'s date from an ISO ``'yyyy-MM-dd'`` string.

    Falls back to the picker's minimum date for invalid or empty values.
    Signals are blocked during the update.
    """
    if picker is None:
        return
    picker.blockSignals(True)
    iso = str(value or "").strip()
    qd = QDate.fromString(iso, "yyyy-MM-dd") if iso else QDate()
    picker.setDate(qd if qd.isValid() else picker.minimumDate())
    picker.blockSignals(False)
