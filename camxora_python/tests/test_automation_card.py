"""Automation card generate button state."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.music.widgets.automation_card import AutomationCard


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_generate_disabled_while_generating(qapp: QApplication) -> None:
    card = AutomationCard()
    card.set_generate_label("Generate (10 Credits)")
    card.set_generate_enabled(True)
    card.set_generating(True)
    assert card._generate_btn.text() == "Generating..."
    assert not card._generate_btn.isEnabled()
    card.set_generating(False)
    assert card._generate_btn.text() == "Generate (10 Credits)"
    assert card._generate_btn.isEnabled()
