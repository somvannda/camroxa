"""Tests for playlist scene timeline sync (Phases 2–4)."""

from __future__ import annotations

from studio.core.models import MediaAsset, new_id
from studio.core.playlist_scene_sync import (
    SCENE_AUDIO,
    SCENE_BACKGROUND,
    SCENE_GRAPHICS,
    find_scene_track,
    has_playlist_scene,
    playlist_content_duration,
    sync_playlist_scene_to_timeline,
)
from studio.core.playlist_settings import PlaylistSettings
from studio.core.project_state import ProjectState


def test_sync_playlist_scene_creates_managed_tracks(tmp_path):
    bg = tmp_path / "bg.png"
    bg.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    state = ProjectState()
    state.project.playlist = PlaylistSettings(
        template_id="glass-romance",
        sub_template_id="minimal-white",
        background_path=str(bg),
    )
    sync_playlist_scene_to_timeline(state, record_undo=False)

    assert has_playlist_scene(state.project)
    bg_track = find_scene_track(state.project, SCENE_BACKGROUND)
    gfx_track = find_scene_track(state.project, SCENE_GRAPHICS)
    assert bg_track is not None
    assert gfx_track is not None
    assert bg_track.locked and gfx_track.locked
    assert len(bg_track.clips) == 1
    assert bg_track.clips[0].kind == "image"
    assert bg_track.clips[0].fit_mode == "cover"
    assert len(gfx_track.clips) == 1
    assert gfx_track.clips[0].kind == "playlist"


def test_sync_playlist_to_timeline_includes_scene_and_audio(sample_audio):
    state = ProjectState()
    media = MediaAsset(
        id="a1",
        name="one.wav",
        type="audio",
        path=str(sample_audio),
        duration=2.0,
    )
    state.add_media(media)
    state.project.playlist = PlaylistSettings(
        template_id="glass-romance",
        sub_template_id="minimal-white",
        song_ids=[media.id],
    )
    state.sync_playlist_to_timeline(record_undo=False)

    audio_track = find_scene_track(state.project, SCENE_AUDIO)
    assert audio_track is not None
    assert len(audio_track.clips) == 1
    assert audio_track.clips[0].media_id == media.id

    gfx = find_scene_track(state.project, SCENE_GRAPHICS)
    assert gfx is not None
    assert gfx.clips[0].duration == playlist_content_duration(state)


def test_playlist_content_duration_sums_songs(sample_audio):
    state = ProjectState()
    media = MediaAsset(
        id="a1",
        name="one.wav",
        type="audio",
        path=str(sample_audio),
        duration=2.0,
    )
    state.add_media(media)
    state.project.playlist.song_ids = [media.id]
    assert playlist_content_duration(state) == 2.0


def test_scene_tracks_reordered_card_above_background():
    state = ProjectState()
    state.project.playlist = PlaylistSettings(template_id="glass-romance", sub_template_id="minimal-white")
    user = state._create_track("video", name="User")
    user.clips.append(
        __import__("core.models", fromlist=["Clip"]).Clip(
            id=new_id("clip"),
            track_id=user.id,
            kind="image",
            label="User clip",
            start=0.0,
            duration=2.0,
        )
    )
    sync_playlist_scene_to_timeline(state, record_undo=False)

    roles = [t.scene_role for t in state.project.tracks]
    bg_idx = roles.index(SCENE_BACKGROUND)
    gfx_idx = roles.index(SCENE_GRAPHICS)
    # Lower index = paints on top in compositor — card must be above background.
    assert gfx_idx < bg_idx
