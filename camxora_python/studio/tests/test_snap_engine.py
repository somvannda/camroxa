import pytest

from studio.core.models import Clip, MediaAsset
from studio.core.project_state import ProjectState, new_id
from studio.core.snap_models import SnapSettings, TimelineMarker
from studio.ui.timeline.snap_engine import (
    SnapContext,
    collect_snap_targets,
    collect_snap_times,
    effective_threshold_sec,
    is_snap_active,
    snap_clip_move,
    snap_clip_trim,
    snap_time,
)


@pytest.fixture
def state_with_clips() -> ProjectState:
    state = ProjectState()
    media = MediaAsset(id="m1", name="a.mp4", type="video", path="/a.mp4", duration=6.0)
    state.add_media(media)
    track = state.add_track("video")
    state.add_clip_from_media(media, track, drop_time=0.0)
    state.add_clip_from_media(media, track, drop_time=10.0)
    state.playhead = 5.0
    state.project.duration = 16.0
    return state


def _ctx(state: ProjectState, **kwargs) -> SnapContext:
    params = {"px_per_sec": 70.0, **kwargs}
    return SnapContext(project_state=state, **params)


def test_s1_snap_disabled_falls_back_to_grid(state_with_clips: ProjectState):
    state_with_clips.project.snap_settings.enabled = False
    result = snap_time(1.234, _ctx(state_with_clips))
    assert result.snapped is False
    assert result.time == pytest.approx(1.25)


def test_s2_alt_temporarily_disables_snap(state_with_clips: ProjectState):
    ctx = _ctx(state_with_clips, temporary_disabled=True)
    assert is_snap_active(ctx) is False
    result = snap_time(5.99, ctx)
    assert result.snapped is False


def test_s3_effective_threshold_clamps_with_zoom():
    settings = SnapSettings(threshold_px=10.0)
    low_zoom = effective_threshold_sec(settings, px_per_sec=20.0)
    high_zoom = effective_threshold_sec(settings, px_per_sec=200.0)
    assert low_zoom <= 0.45
    assert high_zoom >= 0.015
    assert low_zoom > high_zoom


def test_s4_frame_snap_at_high_zoom(state_with_clips: ProjectState):
    settings = state_with_clips.project.snap_settings
    settings.snap_to_frames = True
    settings.frame_rate = 30.0
    # 200 px/sec → frame width 6.67px (> 3px threshold for frame grid)
    ctx = _ctx(state_with_clips, px_per_sec=200.0)
    frame_sec = 1.0 / 30.0
    raw = frame_sec * 5 + 0.01
    result = snap_time(raw, ctx)
    assert result.snapped is True
    assert result.time == pytest.approx(frame_sec * 5)


def test_s5_sequence_end_is_snap_target(state_with_clips: ProjectState):
    times = collect_snap_times(state_with_clips)
    assert state_with_clips.project.duration in times


def test_s6_same_track_edge_beats_playhead(state_with_clips: ProjectState):
    track = state_with_clips.project.tracks[0]
    second = track.clips[1]
    ctx = _ctx(state_with_clips, exclude_clip_id=second.id, track_id=track.id, track_type="video")
    result = snap_clip_move(5.98, second.duration, ctx)
    assert result.snapped is True
    assert result.time == pytest.approx(6.0)
    assert result.edge == "start"


def test_s11_scope_video_excludes_audio_track_targets(state_with_clips: ProjectState):
    audio_media = MediaAsset(id="ma", name="a.mp3", type="audio", path="/a.mp3", duration=4.0)
    state_with_clips.add_media(audio_media)
    audio_track = state_with_clips.add_track("audio")
    state_with_clips.add_clip_from_media(audio_media, audio_track, drop_time=3.0)
    state_with_clips.project.snap_settings.scope = "video"
    targets = collect_snap_targets(_ctx(state_with_clips, track_type="video"))
    target_times_on_audio = [t.time for t in targets if t.track_type == "audio"]
    assert target_times_on_audio == []


def test_s12_locked_track_excluded_from_targets(state_with_clips: ProjectState):
    state_with_clips.project.tracks[0].locked = True
    targets = collect_snap_targets(_ctx(state_with_clips))
    clip_times = [t.time for t in targets if t.kind.startswith("clip")]
    assert clip_times == []


def test_s13_markers_and_in_out_are_targets(state_with_clips: ProjectState):
    state_with_clips.project.markers = [TimelineMarker(id=new_id("mk"), time=3.5, label="A")]
    state_with_clips.project.in_point = 1.0
    state_with_clips.project.out_point = 12.0
    times = collect_snap_times(state_with_clips)
    assert 3.5 in times
    assert 1.0 in times
    assert 12.0 in times


def test_s14_beat_grid_when_enabled(state_with_clips: ProjectState):
    state_with_clips.project.snap_settings.snap_to_beats = True
    state_with_clips.project.bpm = 120.0
    targets = collect_snap_targets(_ctx(state_with_clips))
    beat_times = [t.time for t in targets if t.kind == "beat"]
    assert 0.0 in beat_times
    assert 0.5 in beat_times


def test_s17_center_snap(state_with_clips: ProjectState):
    track = state_with_clips.project.tracks[0]
    clip = track.clips[0]
    second = track.clips[1]
    center = clip.start + clip.duration / 2.0
    ctx = _ctx(
        state_with_clips,
        exclude_clip_id=second.id,
        track_id=track.id,
        track_type="video",
    )
    result = snap_time(center + 0.02, ctx)
    assert result.snapped is True
    assert result.time == pytest.approx(center)
    assert result.edge == "center"


def test_s18_nearby_guides_lists_all_candidates(state_with_clips: ProjectState):
    state_with_clips.playhead = 6.0
    track = state_with_clips.project.tracks[0]
    second = track.clips[1]
    ctx = _ctx(state_with_clips, exclude_clip_id=second.id, track_id=track.id, track_type="video")
    result = snap_clip_move(5.98, second.duration, ctx)
    assert result.active_guide is not None
    assert len(result.nearby_guides) >= 1


def test_trim_right_at_zero_does_not_snap_end_to_playhead(state_with_clips: ProjectState):
    """Clips starting at 00:00 must still expand right — end must not snap to t=0."""
    state_with_clips.playhead = 0.0
    track = state_with_clips.project.tracks[0]
    clip = Clip(
        id=new_id("c"),
        track_id=track.id,
        kind="image",
        label="still",
        start=0.0,
        duration=0.3,
    )
    track.clips.append(clip)
    ctx = SnapContext(
        project_state=state_with_clips,
        px_per_sec=20.0,
        exclude_clip_id=clip.id,
        track_id=track.id,
        track_type=track.type,
    )
    _start, duration, result = snap_clip_trim(clip, "trim_right", 0.0, 1.5, ctx)
    assert duration > 0.3
    assert result.snapped is False or result.time > 0.5
