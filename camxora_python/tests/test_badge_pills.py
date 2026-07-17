"""Tests for global badge/pill tone helpers."""

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy

from shared.themes.badge_pills import (
    BADGE_DANGER,
    BADGE_INFO,
    BADGE_MUTED,
    BADGE_PAD_H,
    BADGE_PAD_V,
    BADGE_ROLE,
    BADGE_STAGE,
    BADGE_SUCCESS,
    BADGE_WARNING,
    apply_badge_pill,
    format_badge_text,
    role_pill_object_name,
    stage_pill_object_name,
    stage_tone_object_name,
    status_pill_object_name,
)
from shared.themes.deep_blue import MAIN_STYLESHEET
from shared.widgets.settings_ui import ProfileIdentityCard


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setStyleSheet(MAIN_STYLESHEET)
    return app


def test_role_pill_is_neutral() -> None:
    assert role_pill_object_name("primary") == BADGE_ROLE
    assert role_pill_object_name("secondary") == BADGE_ROLE


def test_stage_pill_uses_sky_for_pipeline() -> None:
    assert stage_pill_object_name("Converter") == BADGE_STAGE
    assert stage_pill_object_name("Merger") == BADGE_STAGE
    assert stage_pill_object_name("Music") == BADGE_STAGE
    assert stage_pill_object_name("Done") == BADGE_SUCCESS
    assert stage_pill_object_name("Error") == BADGE_DANGER


def test_status_pill_partial_is_amber() -> None:
    assert status_pill_object_name("Partial") == BADGE_WARNING
    assert status_pill_object_name("Completed") == BADGE_SUCCESS
    assert status_pill_object_name("Failed") == BADGE_DANGER
    assert status_pill_object_name("Ready") == BADGE_MUTED
    assert status_pill_object_name("Not started") == BADGE_MUTED
    assert status_pill_object_name("In progress") == BADGE_INFO
    assert status_pill_object_name("Generating") == BADGE_INFO


def test_status_pill_connected_is_success() -> None:
    assert status_pill_object_name("Connected") == BADGE_SUCCESS
    assert status_pill_object_name("Verified") == BADGE_SUCCESS
    assert status_pill_object_name("Not connected") == BADGE_MUTED


def test_stage_and_status_differ_for_header_chips() -> None:
    """Primary/Converter/Partial must not all collapse to the same sky pill."""
    assert role_pill_object_name("primary") == BADGE_ROLE
    assert stage_pill_object_name("Converter") == BADGE_STAGE
    assert status_pill_object_name("Partial") == BADGE_WARNING
    assert len({role_pill_object_name("primary"), stage_pill_object_name("Converter"), status_pill_object_name("Partial")}) == 3


def test_legacy_stage_tone_prefers_status_semantics() -> None:
    assert stage_tone_object_name("Converter", "Partial") == BADGE_WARNING
    assert stage_tone_object_name("Converter", "Completed") == BADGE_SUCCESS


def test_format_badge_text_has_no_unicode_prefixes() -> None:
    assert format_badge_text("Partial", BADGE_WARNING) == "Partial"
    assert format_badge_text("Completed", BADGE_SUCCESS) == "Completed"
    assert format_badge_text("Failed", BADGE_DANGER) == "Failed"
    assert format_badge_text("In progress", BADGE_INFO) == "In progress"
    assert format_badge_text("Primary", BADGE_ROLE) == "Primary"
    assert format_badge_text("Converter", BADGE_STAGE) == "Converter"
    assert format_badge_text("Ready", BADGE_MUTED) == "Ready"
    assert format_badge_text("Partial", BADGE_WARNING, with_icon=True) == "Partial"
    assert format_badge_text("DONE", BADGE_SUCCESS) == "DONE"
    assert format_badge_text("Verified", BADGE_SUCCESS) == "Verified"
    assert format_badge_text("Not started", BADGE_MUTED) == "Not started"
    assert format_badge_text("Connected", BADGE_SUCCESS) == "Connected"


def test_selected_run_object_names_match_qss_ids() -> None:
    """Primary / Converter / Partial use badge_* IDs present in deep_blue QSS."""
    assert role_pill_object_name("primary") == "badge_role"
    assert stage_pill_object_name("Converter") == "badge_stage"
    assert status_pill_object_name("Partial") == "badge_warning"
    sheet = MAIN_STYLESHEET
    for name in ("badge_role", "badge_stage", "badge_warning"):
        assert f"QLabel#{name}" in sheet
    # Horizontal inset is owned by apply_badge_pill contentsMargins; QSS keeps
    # padding at 0 so the two do not stack.
    assert "padding-left: 0" in sheet
    assert "padding-right: 0" in sheet
    assert "padding-top: 0" in sheet
    assert "padding-bottom: 0" in sheet
    assert BADGE_PAD_H == 14
    assert BADGE_PAD_V == 3


def test_badge_qss_soft_fills_no_border() -> None:
    """Badge chrome: soft tonal fills, colored text, no border, shorter height."""
    sheet = MAIN_STYLESHEET
    assert "min-height: 18px" in sheet
    assert "border: none" in sheet
    # Soft fills (not shared #1a3a5c slate with border accents)
    assert "background-color: #243040" in sheet  # role slate
    assert "background-color: #1a2e42" in sheet  # stage sky
    assert "background-color: #2d2614" in sheet  # warning amber
    assert "background-color: #16352c" in sheet  # success teal
    assert "color: #93c5fd" in sheet
    assert "color: #fbbf24" in sheet
    assert "color: #6ee7b7" in sheet
    # Badge shared block: soft fills only (no bordered slate chrome)
    badge_block_start = sheet.index("Global badge / pill system")
    badge_block = sheet[badge_block_start : badge_block_start + 3500]
    assert "border: none" in badge_block
    assert "border: 1px solid" not in badge_block
    assert "border-color:" not in badge_block


def test_apply_badge_pill_enforces_contents_margins(qapp: QApplication) -> None:
    del qapp
    for object_name, label in (
        (BADGE_ROLE, "Primary"),
        (BADGE_STAGE, "Converter"),
        (BADGE_WARNING, "Partial"),
        (BADGE_SUCCESS, "Connected"),
    ):
        chip = QLabel()
        apply_badge_pill(chip, object_name, label=label)
        margins = chip.contentsMargins()
        assert margins.left() == BADGE_PAD_H
        assert margins.right() == BADGE_PAD_H
        assert margins.top() == BADGE_PAD_V
        assert margins.bottom() == BADGE_PAD_V
        assert chip.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
        advance = chip.fontMetrics().horizontalAdvance(label)
        assert chip.minimumWidth() >= advance + BADGE_PAD_H * 2
        assert chip.maximumWidth() >= chip.minimumWidth()
        assert chip.sizeHint().width() >= advance + BADGE_PAD_H * 2


def test_profile_identity_connected_uses_apply_badge_pill(qapp: QApplication) -> None:
    """YouTube Connected chip must get contentsMargins — bare objectName left it flush."""
    del qapp
    card = ProfileIdentityCard()
    card.set_identity(
        initials="BP",
        channel_title="Boss Primary",
        source_text="Source: Account profile",
        youtube_status_text="Connected",
        youtube_connected=True,
    )
    chip = card._youtube_status
    assert chip.objectName() == BADGE_SUCCESS
    assert chip.text() == "Connected"
    margins = chip.contentsMargins()
    assert margins.left() == BADGE_PAD_H
    assert margins.right() == BADGE_PAD_H
    assert margins.top() == BADGE_PAD_V
    assert margins.bottom() == BADGE_PAD_V
    advance = chip.fontMetrics().horizontalAdvance("Connected")
    assert chip.minimumWidth() >= advance + BADGE_PAD_H * 2
