"""Automation card generate button state."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.music.widgets.automation_card import (
    AI_STRUCTURE_SENTINEL,
    AutomationCard,
    SUNO_STRUCTURE_SENTINEL,
)


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


def test_plan_summary_under_generate(qapp: QApplication) -> None:
    card = AutomationCard()
    assert card.layout().indexOf(card._generate_btn) < card.layout().indexOf(card._plan_box)
    card.set_plan_lines("4 batches · 40 songs\nTotal 323.2 credits")
    assert not card._plan_box.isHidden()
    assert "40 songs" in card._plan.text()
    card.set_plan_lines("")
    assert card._plan_box.isHidden()


def test_suno_structure_mode_and_shuffle(qapp: QApplication) -> None:
    card = AutomationCard()
    card.set_options(
        descriptions=[("d1", "Desc")],
        structures=[("s1", "Pop Template")],
        moods=[("m1", "Mood")],
    )
    assert card._structure.findData(AI_STRUCTURE_SENTINEL) == 0
    assert card._structure.findData(SUNO_STRUCTURE_SENTINEL) == 1
    assert card._structure.findData("s1") == 2

    card.set_selected_options("d1", SUNO_STRUCTURE_SENTINEL, "m1")
    assert card.is_suno_structure_selected()
    assert card.selected_structure_mode() == "suno"
    assert card.selected_structure_id() == ""
    assert not card._shuffle_structure.isEnabled()
    assert not card.shuffle_structure()

    card.set_selected_options("d1", AI_STRUCTURE_SENTINEL, "m1")
    assert card.selected_structure_mode() == "ai_free"
    assert not card._shuffle_structure.isEnabled()
    assert not card.shuffle_structure()

    card.set_selected_options("d1", "s1", "m1")
    assert card.selected_structure_mode() == "template"
    assert card.selected_structure_id() == "s1"
    assert card._shuffle_structure.isEnabled()


def test_set_shuffle_structure_ignored_while_suno_or_ai_selected(qapp: QApplication) -> None:
    card = AutomationCard()
    card.set_options(
        descriptions=[("d1", "Desc")],
        structures=[("s1", "Pop Template")],
        moods=[("m1", "Mood")],
    )
    card.set_selected_options("d1", "s1", "m1")
    card.set_shuffle_structure(True)
    assert card.shuffle_structure()

    # Settings restore must not re-check Shuffle under free structure modes.
    card.set_selected_options("d1", SUNO_STRUCTURE_SENTINEL, "m1")
    card.set_shuffle_structure(True)
    assert not card._shuffle_structure.isEnabled()
    assert not card._shuffle_structure.isChecked()
    assert not card.shuffle_structure()

    card.set_selected_options("d1", AI_STRUCTURE_SENTINEL, "m1")
    card.set_shuffle_structure(True)
    assert not card._shuffle_structure.isEnabled()
    assert not card.shuffle_structure()

    # Returning to a template re-enables Shuffle; preference can be set again.
    card.set_selected_options("d1", "s1", "m1")
    assert card._shuffle_structure.isEnabled()
    card.set_shuffle_structure(True)
    assert card.shuffle_structure()
