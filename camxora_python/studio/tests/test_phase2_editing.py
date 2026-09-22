import pytest

from studio.core.models import Clip, MediaAsset, Track
from studio.core.project_state import ProjectState


@pytest.fixture
def state_with_two_clips() -> ProjectState:
    state = ProjectState()
    track = state.add_track("video")
    c1 = Clip(id="c1", track_id=track.id, kind="video", label="a", start=0.0, duration=2.0)
    c2 = Clip(id="c2", track_id=track.id, kind="video", label="b", start=2.0, duration=2.0)
    track.clips.extend([c1, c2])
    state.recalc_duration()
    return state


def test_multi_select_and_delete(state_with_two_clips: ProjectState):
    state = state_with_two_clips
    state.select_clips({"c1", "c2"})
    removed = state.delete_selected_clips()
    assert removed == 2
    assert state.project.tracks[0].clips == []
    assert state.selected_clip_ids == set()


def test_ripple_delete_closes_gap(state_with_two_clips: ProjectState):
    state = state_with_two_clips
    state.project.ripple_edit = True
    state.delete_clip("c1")
    assert state.project.tracks[0].clips[0].start == pytest.approx(0.0)
    assert state.project.tracks[0].clips[0].id == "c2"


def test_ripple_move_shifts_downstream(state_with_two_clips: ProjectState):
    state = state_with_two_clips
    state.project.ripple_edit = True
    state.move_clip("c1", new_start_raw=1.0)
    c2 = next(c for c in state.project.tracks[0].clips if c.id == "c2")
    assert c2.start == pytest.approx(3.0)


def test_ripple_trim_right_pushes_next_clip(state_with_two_clips: ProjectState):
    state = state_with_two_clips
    state.project.ripple_edit = True
    state.trim_clip("c1", "right", dt=1.0)
    c2 = next(c for c in state.project.tracks[0].clips if c.id == "c2")
    assert state.project.tracks[0].clips[0].duration == pytest.approx(3.0)
    assert c2.start == pytest.approx(3.0)


def test_nudge_moves_selection(state_with_two_clips: ProjectState):
    state = state_with_two_clips
    state.select_clip("c1")
    state.nudge_selected_clips(0.5)
    c1 = next(c for c in state.project.tracks[0].clips if c.id == "c1")
    assert c1.start == pytest.approx(0.5)


def test_snap_clip_to_edge_left(state_with_two_clips: ProjectState):
    state = state_with_two_clips
    state.select_clip("c2")
    state.snap_clip_to_edge("c2", -1)
    c2 = next(c for c in state.project.tracks[0].clips if c.id == "c2")
    assert c2.start == pytest.approx(2.0)


def test_detach_linked_audio():
    state = ProjectState()
    video_media = MediaAsset(id="mv", name="v.mp4", type="video", path="/v.mp4", duration=5.0)
    audio_media = MediaAsset(id="ma", name="a.mp3", type="audio", path="/a.mp3", duration=5.0)
    state.add_media(video_media)
    state.add_media(audio_media)
    vtrack = state.add_track("video")
    atrack = state.add_track("audio")
    vclip = state.add_clip_from_media(video_media, vtrack, drop_time=0.0)
    aclips_before = len(atrack.clips)
    # Manually link for test if autolink did not create audio
    if not vclip.linked_group_id:
        group = "link_test"
        vclip.linked_group_id = group
        aclip = state.add_clip_from_media(audio_media, atrack, drop_time=0.0)
        aclip.linked_group_id = group
    assert state.detach_linked_audio(vclip.id) is True
    assert vclip.linked_group_id is None
