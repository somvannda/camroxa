from pathlib import Path

from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState
from studio.ui.main_window import MainWindow


def _make_state_with_a_track() -> ProjectState:
    state = ProjectState()
    state.add_track("video")
    return state


def test_main_window_constructs_with_expected_panes(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.library_panel is not None
    assert window.preview_widget is not None
    assert window.timeline_wrap is not None
    assert window.inspector_host is not None
    assert window.topbar.export_btn is not None
    assert window.topbar.save_btn is not None
    assert window.topbar.open_btn is not None


def test_undo_redo_buttons_disabled_initially(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.topbar.undo_btn.isEnabled() is False
    assert window.topbar.redo_btn.isEnabled() is False


def test_add_track_enables_undo_and_undo_removes_it(qtbot):
    state = _make_state_with_a_track()
    window = MainWindow(state)
    qtbot.addWidget(window)

    window.project_state.add_track("audio")
    window._refresh_undo_redo_buttons()
    assert window.topbar.undo_btn.isEnabled() is True
    assert len(window.project_state.project.tracks) == 2

    window._on_undo_clicked()
    assert len(window.project_state.project.tracks) == 1
    assert window.topbar.redo_btn.isEnabled() is True

    window._on_redo_clicked()
    assert len(window.project_state.project.tracks) == 2


def test_save_then_open_round_trips_project(qtbot, tmp_path: Path):
    state = ProjectState()
    state.project.name = "Round Trip Project"
    media = MediaAsset(id="m1", name="a.mp4", type="video", path="/a.mp4", duration=4.0)
    state.add_media(media)
    track = state.add_track("video")
    state.add_clip_from_media(media, track, drop_time=0.0)

    window = MainWindow(state)
    qtbot.addWidget(window)

    out_path = tmp_path / "roundtrip.camxora"
    from core.project_io import save_project

    save_project(window.project_state, out_path)

    fresh_window = MainWindow()
    qtbot.addWidget(fresh_window)

    from core.project_io import load_project

    loaded_state = load_project(out_path)
    fresh_window.project_state.replace_project(loaded_state.project)
    fresh_window._after_project_mutated_externally()

    assert fresh_window.project_state.project.name == "Round Trip Project"
    assert len(fresh_window.project_state.project.tracks) == 1
    assert fresh_window.topbar.project_name_edit.text() == "Round Trip Project"
    assert fresh_window.topbar.undo_btn.isEnabled() is False
