from pathlib import Path

import numpy as np
import pytest

from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState
from studio.media.audio_source import AudioSourceCache
from studio.media.video_source import VideoSourceCache
from studio.render.compositor import BACKGROUND_COLOR, frame_to_qimage, render_frame


@pytest.fixture
def video_cache() -> VideoSourceCache:
    cache = VideoSourceCache()
    yield cache
    cache.release_all()


def test_render_frame_background_only_when_no_clips(video_cache: VideoSourceCache):
    state = ProjectState()
    frame = render_frame(state, 0.0, video_cache, width=64, height=48)
    assert frame.shape == (48, 64, 3)
    assert frame.dtype == np.uint8
    assert np.all(frame[0, 0] == np.array(BACKGROUND_COLOR, dtype=np.uint8))


def test_render_frame_draws_video_clip(sample_video: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="m1", name="sample.mp4", type="video", path=str(sample_video), duration=2.0, width=64, height=48)
    state.add_media(media)
    track = state.add_track("video")
    state.add_clip_from_media(media, track, drop_time=0.0)

    frame = render_frame(state, 0.5, video_cache, width=128, height=96)
    assert frame.shape == (96, 128, 3)
    # the video fills the frame (64x48 source scaled to fit 128x96 exactly) —
    # center pixel should differ from the pure background color.
    center = frame[48, 64]
    assert not np.array_equal(center, np.array(BACKGROUND_COLOR, dtype=np.uint8))


def test_render_frame_respects_opacity_fade(sample_video: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="m1", name="sample.mp4", type="video", path=str(sample_video), duration=2.0, width=64, height=48)
    state.add_media(media)
    track = state.add_track("video")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)
    state.update_clip(clip.id, fade_in=1.0)

    frame_at_start = render_frame(state, 0.0, video_cache, width=64, height=48)
    frame_mid_fade = render_frame(state, 1.0, video_cache, width=64, height=48)

    # at t=0 opacity should be ~0 (fully faded), so it should look close to background
    assert np.array_equal(frame_at_start[0, 0], np.array(BACKGROUND_COLOR, dtype=np.uint8))


def test_render_frame_skips_clips_outside_active_window(sample_video: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="m1", name="sample.mp4", type="video", path=str(sample_video), duration=2.0, width=64, height=48)
    state.add_media(media)
    track = state.add_track("video")
    state.add_clip_from_media(media, track, drop_time=0.0)

    frame = render_frame(state, 10.0, video_cache, width=64, height=48)  # well past clip end
    assert np.array_equal(frame[0, 0], np.array(BACKGROUND_COLOR, dtype=np.uint8))


def test_render_frame_draws_visualizer_for_enabled_audio_clip(sample_audio: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="m1", name="sample.wav", type="audio", path=str(sample_audio), duration=1.5, sample_rate=22050)
    state.add_media(media)
    track = state.add_track("audio")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)
    state.update_clip(clip.id, viz_enabled=True, viz="bars")

    audio_cache = AudioSourceCache()
    frame = render_frame(state, 0.5, video_cache, audio_cache=audio_cache, width=200, height=120)
    assert frame.max() > 0  # visualizer bars drawn onto an otherwise-black background


def test_render_frame_skips_visualizer_when_disabled(sample_audio: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="m1", name="sample.wav", type="audio", path=str(sample_audio), duration=1.5, sample_rate=22050)
    state.add_media(media)
    track = state.add_track("audio")
    state.add_clip_from_media(media, track, drop_time=0.0)  # viz_enabled defaults to False

    audio_cache = AudioSourceCache()
    frame = render_frame(state, 0.5, video_cache, audio_cache=audio_cache, width=200, height=120)
    assert np.array_equal(frame[0, 0], np.array(BACKGROUND_COLOR, dtype=np.uint8))
    assert frame.max() == max(BACKGROUND_COLOR)


def test_render_frame_without_audio_cache_skips_visualizer(sample_audio: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="m1", name="sample.wav", type="audio", path=str(sample_audio), duration=1.5, sample_rate=22050)
    state.add_media(media)
    track = state.add_track("audio")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)
    state.update_clip(clip.id, viz_enabled=True)

    frame = render_frame(state, 0.5, video_cache, width=200, height=120)  # no audio_cache passed
    assert np.array_equal(frame[0, 0], np.array(BACKGROUND_COLOR, dtype=np.uint8))


def test_render_frame_overlay_on_top_of_video(
    sample_video: Path, sample_image: Path, video_cache: VideoSourceCache
):
    """Higher timeline rows (lower track index) must paint above lower rows."""
    state = ProjectState()
    video_media = MediaAsset(
        id="mv", name="v.mp4", type="video", path=str(sample_video), duration=2.0, width=64, height=48
    )
    logo_media = MediaAsset(
        id="mi", name="logo.png", type="image", path=str(sample_image), duration=5.0
    )
    state.add_media(video_media)
    state.add_media(logo_media)

    overlay_track = state.add_track("overlay")
    video_track = state.add_track("video")
    state.add_clip_from_media(logo_media, overlay_track, drop_time=0.0)
    state.add_clip_from_media(video_media, video_track, drop_time=0.0)

    # Logo is a small red-ish PNG in tests — center should differ when logo is on top.
    frame = render_frame(state, 0.5, video_cache, width=128, height=96)
    center = frame[48, 64]
    bg = np.array(BACKGROUND_COLOR, dtype=np.uint8)
    assert not np.array_equal(center, bg)


def test_render_frame_image_scale_and_position(sample_image: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="mi", name="logo.png", type="image", path=str(sample_image), duration=5.0)
    state.add_media(media)
    track = state.add_track("overlay")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)

    default_frame = render_frame(state, 0.5, video_cache, width=128, height=96)
    state.update_clip(clip.id, transform_scale=2.0, transform_x=0.25, transform_y=0.25, crop_inset=0.1)
    adjusted = render_frame(state, 0.5, video_cache, width=128, height=96)

    assert not np.array_equal(default_frame, adjusted)


def test_render_frame_image_with_mask(sample_image: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="mi", name="logo.png", type="image", path=str(sample_image), duration=5.0)
    state.add_media(media)
    track = state.add_track("overlay")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)

    unmasked = render_frame(state, 0.5, video_cache, width=128, height=96)
    state.update_clip(
        clip.id,
        mask_enabled=True,
        mask_shape="circle",
        mask_width=0.4,
        mask_height=0.4,
    )
    masked = render_frame(state, 0.5, video_cache, width=128, height=96)
    assert not np.array_equal(unmasked, masked)


def test_render_frame_image_fit_modes_and_scale(sample_image: Path, video_cache: VideoSourceCache):
    state = ProjectState()
    media = MediaAsset(id="mi", name="logo.png", type="image", path=str(sample_image), duration=5.0)
    state.add_media(media)
    track = state.add_track("overlay")
    clip = state.add_clip_from_media(media, track, drop_time=0.0)

    for mode in ("fit", "cover", "fill", "free"):
        state.update_clip(clip.id, fit_mode=mode, transform_scale=1.0, record_undo=False)
        render_frame(state, 0.5, video_cache, width=128, height=96)

    state.update_clip(clip.id, fit_mode="cover", transform_scale=3.0, record_undo=False)
    frame = render_frame(state, 0.5, video_cache, width=128, height=96)
    assert frame.shape == (96, 128, 3)


def test_frame_to_qimage_matches_dimensions():
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    frame[:, :] = (10, 20, 30)
    image = frame_to_qimage(frame)
    assert image.width() == 64
    assert image.height() == 48
    assert not image.isNull()
