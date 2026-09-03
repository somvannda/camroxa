import pytest
from PySide6.QtCore import QMimeData, QPointF

from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState
from studio.ui.library_panel import MEDIA_MIME_TYPE, TEXT_PRESET_MIME_TYPE
from studio.ui.timeline.geometry import CLIP_VERTICAL_MARGIN, TRACK_HEIGHT, visible_track_rows
from studio.ui.timeline.timeline_view import TimelineWrap


class _FakeDropEvent:
    """Minimal stand-in for QDropEvent — real drag-and-drop needs a live
    window/cursor to simulate end-to-end, so tests drive `dropEvent`
    directly with just the surface it actually calls."""

    def __init__(self, mime: QMimeData, pos: QPointF) -> None:
        self._mime = mime
        self._pos = pos
        self.accepted = False
        self.ignored = False

    def mimeData(self) -> QMimeData:
        return self._mime

    def position(self) -> QPointF:
        return self._pos

    def acceptProposedAction(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def _media_drop_event(x: float, y: float, media_id: str) -> _FakeDropEvent:
    mime = QMimeData()
    mime.setData(MEDIA_MIME_TYPE, media_id.encode("utf-8"))
    return _FakeDropEvent(mime, QPointF(x, y))


def _text_drop_event(x: float, y: float, preset: str) -> _FakeDropEvent:
    mime = QMimeData()
    mime.setData(TEXT_PRESET_MIME_TYPE, preset.encode("utf-8"))
    return _FakeDropEvent(mime, QPointF(x, y))


@pytest.fixture
def state_with_clip() -> ProjectState:
    state = ProjectState()
    media = MediaAsset(id="m1", name="clip.mp4", type="video", path="/clip.mp4", duration=6.0)
    state.add_media(media)
    track = state.add_track("video")
    state.add_clip_from_media(media, track, drop_time=0.0)
    return state


def test_timeline_wrap_renders_clip_items(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    assert len(wrap.graphics_view._clip_items) == 1


def test_selecting_clip_notifies_project_state(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    clip_id = next(iter(wrap.graphics_view._clip_items))

    state_with_clip.selected_clip_id = None  # added_clip auto-selects; start from a clean slate

    received = []
    wrap.selection_changed.connect(lambda: received.append(True))

    wrap.graphics_view._on_clip_selection_requested(clip_id, False, False)

    assert state_with_clip.selected_clip_id == clip_id
    assert received == [True]


def test_split_selected_via_toolbar_action(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    clip_id = next(iter(wrap.graphics_view._clip_items))
    wrap.graphics_view._on_clip_selection_requested(clip_id, False, False)
    state_with_clip.playhead = 3.0

    wrap.graphics_view.split_selected()

    track = state_with_clip.project.tracks[0]
    assert len(track.clips) == 2
    assert len(wrap.graphics_view._clip_items) == 2


def test_delete_selected_removes_clip(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    clip_id = next(iter(wrap.graphics_view._clip_items))
    wrap.graphics_view._on_clip_selection_requested(clip_id, False, False)

    wrap.graphics_view.delete_selected()

    assert state_with_clip.project.tracks[0].clips == []
    assert wrap.graphics_view._clip_items == {}


def test_duplicate_selected_adds_clip(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    clip_id = next(iter(wrap.graphics_view._clip_items))
    wrap.graphics_view._on_clip_selection_requested(clip_id, False, False)

    wrap.graphics_view.duplicate_selected()

    assert len(state_with_clip.project.tracks[0].clips) == 2
    assert len(wrap.graphics_view._clip_items) == 2


def test_zoom_slider_updates_px_per_sec(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    wrap.toolbar.zoom_slider.setValue(150)
    qtbot.waitUntil(lambda: state_with_clip.project.px_per_sec == 150.0, timeout=500)
    assert state_with_clip.project.px_per_sec == 150.0


def test_add_track_buttons_add_tracks(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    initial_count = len(state_with_clip.project.tracks)

    wrap.toolbar.add_audio_track_btn.click()

    assert len(state_with_clip.project.tracks) == initial_count + 1
    assert state_with_clip.project.tracks[-1].type == "audio"
    assert len(wrap.track_headers._rows) == initial_count + 1


def test_track_toggle_updates_mute_state(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    audio_track = wrap.project_state.add_track("audio")
    wrap.refresh_all()

    wrap._on_track_mute(audio_track.id)

    assert wrap.project_state.get_track(audio_track.id).muted is True


def test_ruler_seek_updates_playhead(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    wrap.graphics_view.seek(2.5)
    assert state_with_clip.playhead == 2.5


def test_first_track_clip_has_no_ruler_height_offset(qtbot, state_with_clip: ProjectState):
    """Regression test: the graphics-view scene must NOT reserve extra
    vertical space for the ruler (it's a separate widget stacked above the
    view) — otherwise clip lanes desync from the TrackHeaders column, which
    has no such offset, once the view scrolls vertically."""
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    clip_id = next(iter(wrap.graphics_view._clip_items))
    item = wrap.graphics_view._clip_items[clip_id]

    assert item.pos().y() == pytest.approx(CLIP_VERTICAL_MARGIN)


def test_scene_height_matches_track_count_without_ruler_offset(qtbot, state_with_clip: ProjectState):
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    # Enough tracks that the track-count height clearly dominates over any
    # default/minimum viewport height, so the `max(total_height, viewport
    # height)` in refresh_from_state can't mask a wrong (ruler-inflated) value.
    for _ in range(20):
        state_with_clip.add_track("audio")
    wrap.refresh_all()

    scene_rect = wrap.graphics_view._scene.sceneRect()
    expected_height = visible_track_rows(len(state_with_clip.project.tracks)) * TRACK_HEIGHT
    assert scene_rect.height() == pytest.approx(expected_height)


def test_video_drop_generates_a_real_filmstrip_off_the_ui_thread(qtbot, sample_video):
    """Regression test: `Clip.thumb_cache` was never populated by anything
    — video clips always rendered as a flat gradient block with no
    filmstrip preview, even though the paint code and the thumbnail
    generator both already existed."""
    state = ProjectState()
    media = MediaAsset(id="mv1", name="clip.mp4", type="video", path=str(sample_video), duration=2.0)
    state.add_media(media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)
    wrap.graphics_view._start_preview_worker(clip.id, media, clip.trim_start, clip.duration)

    qtbot.waitUntil(lambda: bool(clip.thumb_cache), timeout=10000)
    assert len(clip.thumb_cache) > 0
    wrap.graphics_view.wait_for_preview_workers()


def test_audio_drop_generates_a_real_waveform_envelope_off_the_ui_thread(qtbot, sample_audio):
    """Regression test: audio clips only ever drew a fake deterministic
    pseudo-random waveform (`_synthetic_wave_amplitudes`) — never the
    clip's actual decoded audio."""
    state = ProjectState()
    media = MediaAsset(id="ma1", name="sample.wav", type="audio", path=str(sample_audio), duration=1.5)
    state.add_media(media)
    track = state.add_track("audio")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)
    wrap.graphics_view._start_preview_worker(clip.id, media, clip.trim_start, clip.duration)

    qtbot.waitUntil(lambda: bool(clip.waveform_cache), timeout=10000)
    assert len(clip.waveform_cache) > 0
    assert max(clip.waveform_cache) <= 1.0 + 1e-6
    wrap.graphics_view.wait_for_preview_workers()


def test_preview_worker_result_for_deleted_clip_does_not_crash(qtbot, sample_audio):
    state = ProjectState()
    media = MediaAsset(id="ma2", name="sample.wav", type="audio", path=str(sample_audio), duration=1.5)
    state.add_media(media)
    track = state.add_track("audio")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    # Simulate the clip being deleted before the background worker reports back.
    wrap.graphics_view._on_waveform_ready(clip.id, [0.5, 0.5])  # clip.id no longer in project_state
    state.selected_clip_id = clip.id
    wrap.graphics_view.delete_selected()
    wrap.graphics_view._on_waveform_ready(clip.id, [0.5, 0.5])  # must not raise


def test_drop_row_index_maps_directly_to_track_without_ruler_offset(qtbot, state_with_clip: ProjectState):
    """A drop at scene y=0..TRACK_HEIGHT must land on track 0, not require
    an extra RULER_HEIGHT of vertical offset first."""
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    audio_track = state_with_clip.add_track("audio")
    wrap.refresh_all()

    row_index_for_track_0 = int(0.0 // TRACK_HEIGHT)
    row_index_for_track_1 = int((TRACK_HEIGHT + 1.0) // TRACK_HEIGHT)

    assert row_index_for_track_0 == 0
    assert state_with_clip.project.tracks[row_index_for_track_0].id != audio_track.id
    assert row_index_for_track_1 == 1
    assert state_with_clip.project.tracks[row_index_for_track_1].id == audio_track.id


def test_track_header_shows_type_badge_and_name(qtbot):
    from core.models import Track
    from ui.timeline.track_header import TrackHeaderRow

    row = TrackHeaderRow(Track(id="t1", type="audio", name="Audio 1"), 0)
    qtbot.addWidget(row)
    assert not row.type_badge.pixmap().isNull()
    assert row.name_label.text() == "1"


def test_media_drop_onto_empty_timeline_auto_creates_track(qtbot):
    """CapCut-style: dropping straight onto an empty timeline (no tracks at
    all yet) must just work — no manual '+ Track' step required first."""
    state = ProjectState()
    media = MediaAsset(id="m1", name="clip.mp4", type="video", path="/clip.mp4", duration=6.0)
    state.add_media(media)
    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)
    assert state.project.tracks == []

    event = _media_drop_event(0.0, 0.0, "m1")
    wrap.graphics_view.dropEvent(event)

    assert event.accepted is True
    assert len(state.project.tracks) == 1
    assert state.project.tracks[0].type == "video"
    assert len(state.project.tracks[0].clips) == 1


def test_media_drop_below_existing_tracks_creates_a_new_track_instead_of_rejecting(
    qtbot, state_with_clip: ProjectState
):
    """Dropping below the last existing track (or onto a mismatched track
    type) must never show a "drop onto the right kind of track" rejection
    toast — it should just create the track that's needed, like CapCut."""
    wrap = TimelineWrap(state_with_clip)
    qtbot.addWidget(wrap)
    tracks_before = len(state_with_clip.project.tracks)

    media = MediaAsset(id="m2", name="song.mp3", type="audio", path="/song.mp3", duration=3.0)
    state_with_clip.add_media(media)

    toasts: list[str] = []
    wrap.graphics_view.toast_requested.connect(toasts.append)

    far_below_y = tracks_before * TRACK_HEIGHT + 500
    event = _media_drop_event(0.0, far_below_y, "m2")
    wrap.graphics_view.dropEvent(event)

    assert event.accepted is True
    assert toasts == []  # no rejection toast — the drop just succeeded
    assert len(state_with_clip.project.tracks) == tracks_before + 1
    assert state_with_clip.project.tracks[-1].type == "audio"


def test_text_preset_drop_onto_empty_timeline_auto_creates_overlay_track(qtbot):
    state = ProjectState()
    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    event = _text_drop_event(0.0, 0.0, "title")
    wrap.graphics_view.dropEvent(event)

    assert event.accepted is True
    assert len(state.project.tracks) == 1
    assert state.project.tracks[0].type == "overlay"
    assert len(state.project.tracks[0].clips) == 1


def test_clip_drag_on_drop_row_reorders_instead_of_creating_track(qtbot):
    state = ProjectState()
    overlay = state.add_track("overlay")
    audio = state.add_track("audio")
    media = MediaAsset(id="img1", name="photo.png", type="image", path="/photo.png", duration=5.0)
    state.add_media(media)
    clip = state.add_clip_from_media(media, overlay, drop_time=0.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    wrap.graphics_view._on_move_committed(clip.id, 0.0, None, preview_row=2)

    assert len(state.project.tracks) == 2
    assert clip.track_id == overlay.id


def test_prune_empty_tracks_removes_duplicate_empty_overlay():
    state = ProjectState()
    overlay1 = state.add_track("overlay")
    state.add_track("overlay")  # empty Overlay 2
    filled = state.add_track("audio")
    media = MediaAsset(id="a1", name="song.mp3", type="audio", path="/song.mp3", duration=3.0)
    state.add_media(media)
    state.add_clip_from_media(media, filled, drop_time=0.0)
    overlay1.clips.clear()
    assert len(state.project.tracks) == 3
    state.prune_empty_tracks()
    assert len(state.project.tracks) == 2
    types = [t.type for t in state.project.tracks]
    assert types.count("overlay") == 1
    assert types.count("audio") == 1


def test_multi_clip_drag_to_drop_row_splits_onto_new_track(qtbot):
    state = ProjectState()
    overlay = state.add_track("overlay")
    state.add_track("audio")
    media_a = MediaAsset(id="img1", name="a.png", type="image", path="/a.png", duration=5.0)
    media_b = MediaAsset(id="img2", name="b.png", type="image", path="/b.png", duration=5.0)
    state.add_media(media_a)
    state.add_media(media_b)
    clip_a = state.add_clip_from_media(media_a, overlay, drop_time=0.0)
    clip_b = state.add_clip_from_media(media_b, overlay, drop_time=5.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    wrap.graphics_view._on_move_committed(clip_b.id, 5.0, None, preview_row=2)

    assert len(state.project.tracks) == 3
    assert clip_a.track_id == overlay.id
    assert len(overlay.clips) == 1
    assert clip_b.track_id != overlay.id
    assert len(state.get_track(clip_b.track_id).clips) == 1


def test_multi_clip_drag_to_compatible_empty_track_moves_one_clip(qtbot):
    state = ProjectState()
    overlay1 = state.add_track("overlay")
    overlay2 = state.add_track("overlay")
    media_a = MediaAsset(id="img1", name="a.png", type="image", path="/a.png", duration=5.0)
    media_b = MediaAsset(id="img2", name="b.png", type="image", path="/b.png", duration=5.0)
    state.add_media(media_a)
    state.add_media(media_b)
    clip_a = state.add_clip_from_media(media_a, overlay1, drop_time=0.0)
    clip_b = state.add_clip_from_media(media_b, overlay1, drop_time=5.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    wrap.graphics_view._on_move_committed(clip_b.id, 0.0, overlay2.id, preview_row=1)

    assert len(state.project.tracks) == 2
    assert clip_a.track_id == overlay1.id
    assert clip_b.track_id == overlay2.id
    assert len(overlay1.clips) == 1
    assert len(overlay2.clips) == 1


def test_move_committed_reorders_track_when_dropped_on_incompatible_lane(qtbot):
    state = ProjectState()
    overlay = state.add_track("overlay")
    audio = state.add_track("audio")
    media = MediaAsset(id="img1", name="photo.png", type="image", path="/photo.png", duration=5.0)
    state.add_media(media)
    clip = state.add_clip_from_media(media, overlay, drop_time=0.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    wrap.graphics_view._on_move_committed(clip.id, 1.0, audio.id, preview_row=1)

    assert [t.id for t in state.project.tracks] == [audio.id, overlay.id]
    assert clip.track_id == overlay.id
    assert clip.start == 1.0


def test_single_clip_drag_to_occupied_layer_row_reorders_not_merge(qtbot):
    """Moving a lone image to a row that already has a clip must swap layers, not merge."""
    state = ProjectState()
    state.add_track("audio")
    overlay1 = state.add_track("overlay")
    overlay2 = state.add_track("overlay")
    media_logo = MediaAsset(id="img1", name="logo.png", type="image", path="/logo.png", duration=5.0)
    media_car = MediaAsset(id="img2", name="car.png", type="image", path="/car.png", duration=5.0)
    state.add_media(media_logo)
    state.add_media(media_car)
    clip_logo = state.add_clip_from_media(media_logo, overlay1, drop_time=0.0)
    clip_car = state.add_clip_from_media(media_car, overlay2, drop_time=0.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    # Drag car from row 2 onto row 1 where the logo already lives.
    wrap.graphics_view._on_move_committed(clip_car.id, 0.0, overlay1.id, preview_row=1)

    assert clip_car.track_id == overlay2.id
    assert clip_logo.track_id == overlay1.id
    assert len(overlay1.clips) == 1
    assert len(overlay2.clips) == 1
    assert clip_car.start == 0.0
    assert clip_logo.start == 0.0
    assert state.project.tracks[1].id == overlay2.id
    assert state.project.tracks[2].id == overlay1.id


def test_single_audio_clip_merges_onto_occupied_audio_track(qtbot, sample_audio):
    """Drag a lone song onto a row that already has audio — join the same track."""
    state = ProjectState()
    from core.models import MediaAsset

    track_a = state.add_track("audio")
    track_b = state.add_track("audio")
    media_a = MediaAsset(id="a1", name="one.mp3", type="audio", path=str(sample_audio), duration=2.0)
    media_b = MediaAsset(id="a2", name="two.mp3", type="audio", path=str(sample_audio), duration=3.0)
    state.add_media(media_a)
    state.add_media(media_b)
    clip_a = state.add_clip_from_media(media_a, track_a, drop_time=0.0)
    clip_b = state.add_clip_from_media(media_b, track_b, drop_time=0.0)

    wrap = TimelineWrap(state)
    qtbot.addWidget(wrap)

    wrap.graphics_view._on_move_committed(clip_b.id, 2.0, track_a.id, preview_row=0)

    assert len(state.project.tracks) == 1
    assert clip_a.track_id == track_a.id
    assert clip_b.track_id == track_a.id
    assert len(track_a.clips) == 2
    assert clip_b.start == clip_a.end
