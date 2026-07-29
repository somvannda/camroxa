"""Tests for preview edit-mode resolution."""

from __future__ import annotations

from features.video.lib.preview_edit_modes import resolve_preview_edit_modes


def test_background_tab_enables_background_edit() -> None:
    background, spectrum, text, lightning = resolve_preview_edit_modes("background")
    assert background is True
    assert spectrum is False
    assert text == ""
    assert lightning is False


def test_spectrum_tab_enables_spectrum_position() -> None:
    background, spectrum, text, lightning = resolve_preview_edit_modes("spectrum")
    assert background is False
    assert spectrum is True
    assert text == ""
    assert lightning is False


def test_lightning_tab_enables_lightning_position() -> None:
    background, spectrum, text, lightning = resolve_preview_edit_modes("lightning")
    assert background is False
    assert spectrum is False
    assert text == ""
    assert lightning is True


def test_logo_tab_disables_canvas_edits() -> None:
    background, spectrum, text, lightning = resolve_preview_edit_modes("logo")
    assert background is False
    assert spectrum is False
    assert text == ""
    assert lightning is False


def test_side_album_focus_wins() -> None:
    background, spectrum, text, lightning = resolve_preview_edit_modes(
        "spectrum",
        "album",
        edit_focus="side",
    )
    assert background is False
    assert spectrum is False
    assert text == "album"
    assert lightning is False


def test_domain_focus_ignores_side_tab() -> None:
    background, spectrum, text, lightning = resolve_preview_edit_modes(
        "spectrum",
        "title",
        edit_focus="domain",
    )
    assert spectrum is True
    assert text == ""
    assert lightning is False


def test_side_title_focus() -> None:
    background, spectrum, text, lightning = resolve_preview_edit_modes(
        "particles",
        "title",
        edit_focus="side",
    )
    assert text == "title"
    assert spectrum is False
    assert lightning is False
