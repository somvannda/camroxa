"""Shell calendar date edit — popup only, no month-stepping arrows.

QDateEdit defaults to spin up/down arrows. With ``MM/dd/yyyy`` the first
section is Month, so a single click on the down arrow advances the month
instead of (or in addition to) opening the calendar. Match Electron's
DatePickerField: open a calendar, do not spin sections.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QAbstractSpinBox, QDateEdit, QDateTimeEdit, QWidget


class ShellDateEdit(QDateEdit):
    """Date field with calendar popup only (no section spin arrows)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("MM/dd/yyyy")
        # Hide spin arrows; calendar popup button remains when calendarPopup is on.
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setCurrentSection(QDateTimeEdit.Section.DaySection)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def stepBy(self, steps: int) -> None:  # noqa: ARG002 — Qt API
        # Never nudge month/day/year from residual arrow/keyboard step buttons.
        return

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Scrolling over the field must not change the date.
        event.ignore()


def make_shell_date_edit(
    *,
    parent: QWidget | None = None,
    object_name: str = "",
    initial: QDate | None = None,
) -> ShellDateEdit:
    """Create a configured shell date edit, optionally seeded with a date."""
    edit = ShellDateEdit(parent)
    if object_name:
        edit.setObjectName(object_name)
    if initial is not None and initial.isValid():
        edit.setDate(initial)
    return edit
