import pytest

from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState


def _video_audio_pair(state: ProjectState) -> tuple:
    video_media = MediaAsset(id="m1", name="clip.mp4", type="video", path="/clip.mp4", duration=6.0)
    audio_media = MediaAsset(id="m1a", name="clip.mp4", type="audio", path="/clip.mp4", duration=6.0)
    state.add_media(video_media)
    state.add_media(audio_media)
    vtrack = state.add_track("video")
    atrack = state.add_track("audio")
    vclip = state.add_clip_from_media(video_media, vtrack, drop_time=0.0)
    aclip = state.add_clip_from_media(audio_media, atrack, drop_time=0.0)
    assert vclip is not None and aclip is not None
    return vclip, aclip


def test_linked_clips_move_together(state: ProjectState | None = None):
    state = state or ProjectState()
    vclip, aclip = _video_audio_pair(state)
    group = "link_test"
    vclip.linked_group_id = group
    aclip.linked_group_id = group

    state.move_clip(vclip.id, new_start_raw=2.0)

    assert vclip.start == pytest.approx(2.0)
    assert aclip.start == pytest.approx(2.0)


def test_locked_track_clip_does_not_move_with_linked_group():
    state = ProjectState()
    vclip, aclip = _video_audio_pair(state)
    atrack = state.project.tracks[1]
    atrack.locked = True
    group = "link_test"
    vclip.linked_group_id = group
    aclip.linked_group_id = group

    state.move_clip(vclip.id, new_start_raw=3.0)

    assert vclip.start == pytest.approx(3.0)
    assert aclip.start == pytest.approx(0.0)


def test_autolink_companion_clips_same_media_and_time():
    from core.models import Clip
    from core.project_state import new_id
    from core.time_utils import snap

    state = ProjectState()
    media = MediaAsset(id="m1", name="clip.mp4", type="video", path="/clip.mp4", duration=6.0)
    state.add_media(media)
    vtrack = state.add_track("video")
    atrack = state.add_track("audio")
    vclip = state._insert_clip_from_media(media, vtrack, 0.0)
    aclip = Clip(
        id=new_id("clip"),
        track_id=atrack.id,
        media_id=media.id,
        kind="audio",
        label=media.name,
        start=snap(0.0),
        duration=6.0,
    )
    atrack.clips.append(aclip)
    audio_media = MediaAsset(id="m1a", name="clip.mp4", type="audio", path="/clip.mp4", duration=6.0)
    state._autolink_companion_clips(aclip, audio_media)

    assert vclip.linked_group_id is not None
    assert aclip.linked_group_id == vclip.linked_group_id
