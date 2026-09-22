import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QTextEdit

from studio.core.models import Clip, MediaAsset
from studio.core.project_state import ProjectState
from studio.ui.animation_preset_grid import AnimationPresetGrid
from studio.ui.clip_inspector_controls import ImageFitModeRow
from studio.ui.clip_inspector_tabs import InspectorTabRow
from studio.ui.inspector_panel import InspectorPanel, _ClipTextEdit


@pytest.fixture
def state_with_text_clip() -> ProjectState:
    state = ProjectState()
    track = state.add_track("overlay")
    state.add_text_clip(track, "title", drop_time=0.0)  # auto-selects the new clip
    return state


def _find_text_edit(panel: InspectorPanel) -> QTextEdit:
    edits = panel.findChildren(QTextEdit)
    assert len(edits) == 1
    return edits[0]


def test_typing_does_not_mutate_clip_or_push_undo_immediately(qtbot, state_with_text_clip: ProjectState):
    panel = InspectorPanel(state_with_text_clip)
    qtbot.addWidget(panel)
    undo_depth_before = len(state_with_text_clip._undo_stack)
    original_text = state_with_text_clip.get_clip(state_with_text_clip.selected_clip_id)[1].text

    text_edit = _find_text_edit(panel)
    for ch in "Hello World":
        text_edit.insertPlainText(ch)  # simulate keystrokes one at a time

    clip = state_with_text_clip.get_clip(state_with_text_clip.selected_clip_id)[1]
    assert clip.text == original_text  # not committed yet
    assert len(state_with_text_clip._undo_stack) == undo_depth_before  # no per-keystroke undo spam


def test_typing_does_not_rebuild_the_text_edit_widget(qtbot, state_with_text_clip: ProjectState):
    panel = InspectorPanel(state_with_text_clip)
    qtbot.addWidget(panel)
    text_edit = _find_text_edit(panel)

    for ch in "abc":
        text_edit.insertPlainText(ch)
        assert _find_text_edit(panel) is text_edit  # same widget instance throughout


def test_losing_focus_commits_exactly_once(qtbot, state_with_text_clip: ProjectState):
    panel = InspectorPanel(state_with_text_clip)
    qtbot.addWidget(panel)
    undo_depth_before = len(state_with_text_clip._undo_stack)
    clip_id = state_with_text_clip.selected_clip_id

    text_edit = _find_text_edit(panel)
    text_edit.clear()
    for ch in "New Caption":
        text_edit.insertPlainText(ch)

    panel._commit_pending_text_edit()  # simulates the focus_lost commit path

    clip = state_with_text_clip.get_clip(clip_id)[1]
    assert clip.text == "New Caption"
    assert len(state_with_text_clip._undo_stack) == undo_depth_before + 1  # exactly one undo step

    # committing again with no further edits must be a no-op
    panel._commit_pending_text_edit()
    assert len(state_with_text_clip._undo_stack) == undo_depth_before + 1


def test_selecting_away_commits_pending_edit_before_rebuilding(qtbot, state_with_text_clip: ProjectState):
    panel = InspectorPanel(state_with_text_clip)
    qtbot.addWidget(panel)
    clip_id = state_with_text_clip.selected_clip_id

    text_edit = _find_text_edit(panel)
    text_edit.clear()
    for ch in "Committed on switch":
        text_edit.insertPlainText(ch)

    state_with_text_clip.selected_clip_id = None
    panel.refresh()  # e.g. triggered by selecting a different/no clip on the timeline

    clip = state_with_text_clip.get_clip(clip_id)[1]
    assert clip.text == "Committed on switch"


def test_focus_out_event_emits_focus_lost_signal(qtbot):
    widget = _ClipTextEdit()
    qtbot.addWidget(widget)
    received = []
    widget.focus_lost.connect(lambda: received.append(True))

    widget.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))

    assert received == [True]


def test_animation_grid_image_has_four_sub_tabs(qtbot):
    grid = AnimationPresetGrid(for_image=True)
    qtbot.addWidget(grid)
    tabs = grid.findChildren(InspectorTabRow)[0]
    assert len(tabs._buttons) == 4
    assert [b.text() for b in tabs._buttons] == ["In", "Out", "Combo", "Audio"]


def test_animation_grid_video_has_three_sub_tabs(qtbot):
    grid = AnimationPresetGrid(for_image=False)
    qtbot.addWidget(grid)
    tabs = grid.findChildren(InspectorTabRow)[0]
    assert len(tabs._buttons) == 3


def test_fit_mode_deselect_restores_pre_fit_transform(qtbot):
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        transform_scale=0.4,
        transform_x=0.3,
        transform_y=0.7,
        fit_mode="free",
    )
    changes: list[dict] = []

    row = ImageFitModeRow(clip, on_preview=lambda **_f: None, on_change=lambda **f: changes.append(f))
    qtbot.addWidget(row)

    row._select("cover")
    assert changes[-1]["transform_scale"] == 1.0

    row._select("fit")
    assert changes[-1]["fit_mode"] == "fit"

    row._select("fit")  # toggle off
    assert changes[-1]["fit_mode"] == "free"
    assert changes[-1]["transform_scale"] == 0.4
    assert changes[-1]["transform_x"] == 0.3
    assert changes[-1]["transform_y"] == 0.7


def test_fit_mode_deselect_syncs_scale_slider(qtbot):
    state = ProjectState()
    track = state.add_track("overlay")
    media = MediaAsset(id="m1", name="img.png", type="image", path="/img.png", duration=5.0)
    state.add_media(media)
    clip = state.add_clip_from_media(media, track, drop_time=0.0)
    state.update_clip(clip.id, transform_scale=0.4, record_undo=False)

    panel = InspectorPanel(state)
    qtbot.addWidget(panel)

    fit_row = panel.findChild(ImageFitModeRow)
    assert fit_row is not None
    fit_row._select("cover")
    assert panel._scale_field is not None
    assert panel._scale_field.value() == pytest.approx(100.0)

    fit_row._select("cover")
    assert panel._scale_field.value() == pytest.approx(40.0)
    live = state.get_clip(clip.id)[1]
    assert live.transform_scale == pytest.approx(0.4)
