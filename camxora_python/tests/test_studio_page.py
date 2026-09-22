"""Studio page smoke tests — page builds and pauses playback when left."""

from __future__ import annotations

from features.studio.views.studio_view import StudioView


def test_studio_view_builds_editor(qapp) -> None:
    view = StudioView()
    assert view._editor is not None
    # Editor exposes the playback controller used by the page lifecycle hook.
    assert view._editor.playback_controller is not None
    assert view._editor.project_state is not None


def test_studio_view_deactivate_pauses_playback(qapp) -> None:
    view = StudioView()
    state = view._editor.project_state
    # Simulate an active playback state, then leave the page.
    state.is_playing = True
    view.deactivate_page()
    assert state.is_playing is False
