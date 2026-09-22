import pytest

from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState


@pytest.fixture
def state() -> ProjectState:
    return ProjectState()


@pytest.fixture
def video_media() -> MediaAsset:
    return MediaAsset(id="m_video", name="clip.mp4", type="video", path="/clip.mp4", duration=6.0)


def test_add_track_default_names(state: ProjectState):
    t1 = state.add_track("video")
    t2 = state.add_track("video")
    assert t1.name == "1"
    assert t2.name == "2"


def test_first_clip_on_empty_track_snaps_to_zero(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=2.5)
    assert clip.start == 0.0


def test_second_clip_on_track_respects_drop_time(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    first = state.add_clip_from_media(video_media, track, drop_time=0.0)
    second = state.add_clip_from_media(video_media, track, drop_time=2.0)
    # overlaps first (0..6 vs 2..8) — resolve_overlap pushes to first.end
    assert second.start == first.end


def test_add_clip_from_media_rejects_wrong_track_type(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    audio_track = state.add_track("audio")
    clip = state.add_clip_from_media(video_media, audio_track, drop_time=0.0)
    assert clip is None
    assert audio_track.clips == []


def test_add_clip_from_media_at_row_creates_track_when_no_track_exists(state: ProjectState, video_media: MediaAsset):
    """CapCut-style drop: no pre-existing track is required — dropping onto
    an empty timeline (row_index out of range) auto-creates the right kind
    of track."""
    state.add_media(video_media)
    assert state.project.tracks == []
    clip = state.add_clip_from_media_at_row(video_media, row_index=0, drop_time=0.0)
    assert len(state.project.tracks) == 1
    assert state.project.tracks[0].type == "video"
    assert clip.track_id == state.project.tracks[0].id


def test_add_clip_from_media_at_row_creates_new_track_on_type_mismatch(state: ProjectState, video_media: MediaAsset):
    """Dropping a video onto a row that maps to an existing audio track
    must not reject the drop (real editors never do) — it creates a fresh
    video track instead of reusing the mismatched one."""
    state.add_media(video_media)
    audio_track = state.add_track("audio")
    clip = state.add_clip_from_media_at_row(video_media, row_index=0, drop_time=0.0)
    assert audio_track.clips == []
    assert len(state.project.tracks) == 2
    new_track = state.get_track(clip.track_id)
    assert new_track is not None and new_track.type == "video"


def test_add_clip_from_media_at_row_reuses_matching_track(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media_at_row(video_media, row_index=0, drop_time=0.0)
    assert len(state.project.tracks) == 1
    assert clip.track_id == track.id


def test_add_clip_from_media_at_row_is_a_single_undo_step(state: ProjectState, video_media: MediaAsset):
    """Auto-creating a track and inserting the clip is one user gesture
    (one drag-and-drop) and must undo in one step, not two."""
    state.add_media(video_media)
    undo_depth_before = len(state._undo_stack)
    state.add_clip_from_media_at_row(video_media, row_index=0, drop_time=0.0)
    assert len(state._undo_stack) == undo_depth_before + 1
    state.undo()
    assert state.project.tracks == []


def test_add_text_clip_at_row_creates_overlay_track_when_missing(state: ProjectState):
    clip = state.add_text_clip_at_row("title", row_index=0, drop_time=0.0)
    assert clip is not None
    assert len(state.project.tracks) == 1
    assert state.project.tracks[0].type == "overlay"


def test_add_clip_from_media_snaps_start_and_selects(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=1.234)
    assert clip is not None
    assert clip.start == 0.0  # first clip on empty track always starts at 0
    assert clip.duration == 6.0
    assert state.selected_clip_id == clip.id
    assert state.project.duration == pytest.approx(6.0)


def test_resolve_overlap_pushes_clip_forward(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    first = state.add_clip_from_media(video_media, track, drop_time=0.0)
    second = state.add_clip_from_media(video_media, track, drop_time=2.0)
    assert first is not None and second is not None
    # second overlaps first (0..6 vs 2..8) so it should be pushed to start at first.end
    assert second.start == first.end


def test_move_clip_clamps_to_zero_and_snaps(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    state.move_clip(clip.id, new_start_raw=-5.0)
    assert clip.start == 0.0
    state.move_clip(clip.id, new_start_raw=3.234)
    assert clip.start == 3.25


def test_trim_right_extends_within_media_and_respects_min_duration(state: ProjectState):
    media = MediaAsset(id="m_long", name="long.mp4", type="video", path="/long.mp4", duration=10.0)
    state = ProjectState()
    state.add_media(media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)
    state.trim_clip(clip.id, "right", dt=-3.0)
    assert clip.duration == 7.0
    state.trim_clip(clip.id, "right", dt=2.0)
    assert clip.duration == 9.0
    state.trim_clip(clip.id, "right", dt=-100.0)
    assert clip.duration == 0.2


def test_trim_right_cannot_exceed_media_duration(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    state.trim_clip(clip.id, "right", dt=-2.0)
    assert clip.duration == 4.0
    state.trim_clip(clip.id, "right", dt=100.0)
    assert clip.duration == 6.0


def test_trim_left_cannot_extend_before_media_start(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    state.trim_clip(clip.id, "left", dt=1.0)
    assert clip.start == 1.0
    assert clip.trim_start == 1.0
    state.trim_clip(clip.id, "left", dt=-10.0)
    assert clip.start == 0.0
    assert clip.trim_start == 0.0
    assert clip.duration == 6.0


def test_trim_left_adjusts_start_and_trim_start(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=2.0)
    clip.start = 2.0  # placed after first-clip-at-zero rule for trim geometry test
    orig_duration = clip.duration
    state.trim_clip(clip.id, "left", dt=1.0)
    assert clip.start == 3.0
    assert clip.trim_start == 1.0
    assert clip.duration == orig_duration - 1.0


def test_trim_right_clamps_at_next_clip_instead_of_overlapping(state: ProjectState):
    media = MediaAsset(id="m_gap", name="long.mp4", type="video", path="/long.mp4", duration=20.0)
    state.add_media(media)
    track = state.add_track("video")
    first = state.add_clip_from_media(media, track, drop_time=0.0)
    state.trim_clip(first.id, "right", dt=-14.0)  # 0..6
    second = state.add_clip_from_media(media, track, drop_time=10.0)  # 10..30

    state.trim_clip(first.id, "right", dt=10.0)  # try to extend to 16, past `second` at 10

    assert first.duration == pytest.approx(10.0)
    assert first.end == pytest.approx(second.start)


def test_trim_left_clamps_at_previous_clip_instead_of_overlapping(state: ProjectState):
    media = MediaAsset(id="m_gap2", name="long.mp4", type="video", path="/long.mp4", duration=20.0)
    state.add_media(media)
    track = state.add_track("video")
    first = state.add_clip_from_media(media, track, drop_time=0.0)
    state.trim_clip(first.id, "right", dt=-14.0)  # 0..6
    second = state.add_clip_from_media(media, track, drop_time=6.0)
    state.trim_clip(second.id, "left", dt=2.0)  # 8..20 with trim_start=2

    state.trim_clip(second.id, "left", dt=-5.0)  # try to extend back past `first` at 6

    assert second.start == pytest.approx(first.end)
    assert second.start >= first.end


def test_trim_with_zero_movement_is_a_no_op_and_does_not_push_undo(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    orig_start, orig_duration = clip.start, clip.duration
    undo_depth_before = len(state._undo_stack)

    state.trim_clip(clip.id, "right", dt=0.0)
    state.trim_clip(clip.id, "left", dt=0.0)

    assert clip.start == orig_start
    assert clip.duration == orig_duration
    assert len(state._undo_stack) == undo_depth_before


def test_split_at_playhead_creates_two_clips(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    state.playhead = 2.0
    right = state.split_clip_at_playhead(clip.id)
    assert right is not None
    assert clip.duration == 2.0
    assert right.start == 2.0
    assert right.duration == 4.0
    assert right.trim_start == 2.0
    assert len(track.clips) == 2


def test_split_outside_clip_bounds_returns_none(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    state.playhead = 10.0
    assert state.split_clip_at_playhead(clip.id) is None


def test_duplicate_clip_appends_after_original(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    dup = state.duplicate_clip(clip.id)
    assert dup is not None
    assert dup.id != clip.id
    assert dup.start == clip.end
    assert len(track.clips) == 2


def test_delete_clip_removes_and_clears_selection(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    assert state.delete_clip(clip.id) is True
    assert track.clips == []
    assert state.selected_clip_id is None


def test_undo_redo_round_trip(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)
    assert len(track.clips) == 1

    state.delete_clip(clip.id)
    assert state.get_track(track.id) is not None
    assert state.get_track(track.id).clips == []

    assert state.undo() is True
    assert len(state.get_track(track.id).clips) == 1

    assert state.redo() is True
    assert state.get_track(track.id).clips == []

    assert state.undo() is True
    assert state.can_redo() is True


def test_has_timeline_clips(state: ProjectState, video_media: MediaAsset):
    assert state.has_timeline_clips() is False
    state.add_media(video_media)
    track = state.add_track("video")
    state.add_clip_from_media(video_media, track, drop_time=0.0)
    assert state.has_timeline_clips() is True


def test_active_clips_at_time_and_hidden_track(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(video_media, track, drop_time=0.0)

    active = state.active_clips_at(2.0)
    assert (track, clip) in active.video

    state.toggle_track_hidden(track.id)
    active_hidden = state.active_clips_at(2.0)
    assert active_hidden.video == []


def test_compute_opacity_applies_fade_in_and_out():
    from core.models import Clip

    clip = Clip(
        id="c1", track_id="t1", kind="video", label="x",
        start=0.0, duration=10.0, fade_in=2.0, fade_out=2.0, opacity=1.0,
    )
    assert ProjectState.compute_opacity(clip, 0.0) == pytest.approx(0.0)
    assert ProjectState.compute_opacity(clip, 1.0) == pytest.approx(0.5)
    assert ProjectState.compute_opacity(clip, 5.0) == pytest.approx(1.0)
    assert ProjectState.compute_opacity(clip, 9.0) == pytest.approx(0.5)


def test_add_text_clip_uses_preset_defaults(state: ProjectState):
    track = state.add_track("overlay")
    clip = state.add_text_clip(track, "title", drop_time=0.0)
    assert clip is not None
    assert clip.text == "Your Title Here"
    assert clip.size == 52
    assert clip.kind == "text"


def test_image_clip_can_extend_beyond_source_duration(state: ProjectState):
    media = MediaAsset(id="m_img", name="photo.png", type="image", path="/photo.png", duration=5.0)
    state.add_media(media)
    track = state.add_track("overlay")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)
    assert state.clip_media_max_duration(clip) is None
    state.trim_clip(clip.id, "right", dt=120.0)
    assert clip.duration == pytest.approx(125.0)


def test_image_clip_can_extend_left_on_timeline(state: ProjectState):
    media = MediaAsset(id="m_img2", name="photo.png", type="image", path="/photo.png", duration=5.0)
    state.add_media(media)
    track = state.add_track("overlay")
    clip = state.add_clip_from_media(media, track, drop_time=4.0)
    clip.start = 4.0
    assert clip.start == 4.0
    orig_duration = clip.duration
    state.trim_clip(clip.id, "left", dt=-2.0)
    assert clip.start == pytest.approx(2.0)
    assert clip.duration == pytest.approx(orig_duration + 2.0)
    assert clip.trim_start == 0.0


def test_move_clip_to_track_changes_track_and_resolves_overlap(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    v1 = state.add_track("video")
    v2 = state.add_track("video")
    clip = state.add_clip_from_media(video_media, v1, drop_time=0.0)
    state.move_clip_to_track(clip.id, v2.id, new_start_raw=2.0)
    assert clip.track_id == v2.id
    assert clip.start == 2.0
    assert clip not in v1.clips
    assert clip in v2.clips


def test_move_clip_to_track_rejects_incompatible_track(state: ProjectState, video_media: MediaAsset):
    state.add_media(video_media)
    video = state.add_track("video")
    audio = state.add_track("audio")
    clip = state.add_clip_from_media(video_media, video, drop_time=0.0)
    state.move_clip_to_track(clip.id, audio.id, new_start_raw=1.0)
    assert clip.track_id == video.id
