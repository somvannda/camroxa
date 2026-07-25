"""Shell date edit — calendar popup without month-stepping arrows."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QAbstractSpinBox, QApplication

from shared.widgets.shell_date_edit import ShellDateEdit, make_shell_date_edit


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_shell_date_edit_hides_spin_buttons(qapp: QApplication) -> None:
    edit = make_shell_date_edit()
    assert edit.calendarPopup() is True
    assert edit.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert edit.displayFormat() == "MM/dd/yyyy"


def test_step_by_does_not_change_date(qapp: QApplication) -> None:
    edit = ShellDateEdit()
    before = edit.date()
    edit.stepBy(-1)
    edit.stepBy(1)
    assert edit.date() == before
