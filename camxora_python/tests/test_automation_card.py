"""Automation card generate button state."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QFrame

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
    assert card.layout().indexOf(card._generate_btn) < card.layout().indexOf(card._costs_host)
    assert card.layout().indexOf(card._generate_btn) < card.layout().indexOf(card._plan_box)
    card.set_plan_summary(
        batches=1,
        songs=9,
        image_jobs=4,
        draft_credits=5.4009,
        suno_credits=90,
        image_credits=4,
        total_credits=99.40090000000001,
        video_enabled=True,
        video_ops=18,
        merge_ops=2,
        video_credits=74,
    )
    assert not card._plan_box.isHidden()
    assert card._batch_value.text() == "1 batch"
    assert card._song_value.text() == "9 songs"
    assert card._video_value.text() == "18 export · 2 merge"
    assert card._video_credits.text() == "74"
    assert card._total_credits.text() == "99.4"
    rules = [
        frame
        for frame in card._plan_metrics.findChildren(QFrame)
        if frame.objectName() == "PlanColumnRule"
    ]
    assert len(rules) == 7
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
