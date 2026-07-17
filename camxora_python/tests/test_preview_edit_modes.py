"""Tests for preview edit-mode resolution."""

from __future__ import annotations

from features.video.lib.preview_edit_modes import resolve_preview_edit_modes


def test_background_tab_enables_background_canvas_edit() -> None:
    background, spectrum, text = resolve_preview_edit_modes("background")
    assert background is True
    assert spectrum is False
    assert text == ""


def test_spectrum_tab_enables_position_edit() -> None:
    background, spectrum, text = resolve_preview_edit_modes("spectrum")
    assert background is False
    assert spectrum is True
    assert text == ""


def test_other_tabs_disable_canvas_edits() -> None:
    background, spectrum, text = resolve_preview_edit_modes("logo")
    assert background is False
    assert spectrum is False
    assert text == ""


def test_album_side_focus_enables_album_drag() -> None:
    background, spectrum, text = resolve_preview_edit_modes(
        "spectrum",
        "album",
        edit_focus="side",
    )
    assert background is False
    assert spectrum is False
    assert text == "album"


def test_title_side_focus_enables_title_drag() -> None:
    background, spectrum, text = resolve_preview_edit_modes(
        "background",
        "title",
        edit_focus="side",
    )
    assert background is False
    assert spectrum is False
    assert text == "title"


def test_domain_focus_ignores_side_tab_for_spectrum() -> None:
    background, spectrum, text = resolve_preview_edit_modes(
        "spectrum",
        "album",
        edit_focus="domain",
    )
    assert background is False
    assert spectrum is True
    assert text == ""
