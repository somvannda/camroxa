from pathlib import Path

import numpy as np
import pytest

from studio.audio.mixer import AudioMixer
from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState


@pytest.fixture
def state_with_audio_clip(sample_audio: Path) -> tuple[ProjectState, str]:
    state = ProjectState()
    media = MediaAsset(id="m1", name="sample.wav", type="audio", path=str(sample_audio), duration=1.5, sample_rate=22050)
    state.add_media(media)
    track = state.add_track("audio")
    state.add_clip_from_media(media, track, drop_time=0.0)
    return state, track.id


def test_mix_block_produces_audio_within_clip_range(state_with_audio_clip):
    state, _track_id = state_with_audio_clip
    mixer = AudioMixer(state, sample_rate=22050, channels=2, block_size=512)
    block = mixer.mix_block(0.5, 512)
    assert block.shape == (512, 2)
    assert np.abs(block).max() > 0.0


def test_mix_block_silent_when_track_muted(state_with_audio_clip):
    state, track_id = state_with_audio_clip
    state.toggle_track_mute(track_id)
    mixer = AudioMixer(state, sample_rate=22050, channels=2, block_size=512)
    block = mixer.mix_block(0.5, 512)
    assert np.abs(block).max() == 0.0


def test_mix_block_silent_outside_active_range(state_with_audio_clip):
    state, _track_id = state_with_audio_clip
    mixer = AudioMixer(state, sample_rate=22050, channels=2, block_size=512)
    block = mixer.mix_block(10.0, 512)
    assert np.abs(block).max() == 0.0


def test_mix_block_scales_with_volume(state_with_audio_clip):
    state, _track_id = state_with_audio_clip
    clip_id = state.selected_clip_id
    mixer = AudioMixer(state, sample_rate=22050, channels=2, block_size=512)
    full = mixer.mix_block(0.5, 512)

    state.update_clip(clip_id, volume=0.25)
    quiet = mixer.mix_block(0.5, 512)
    assert np.abs(quiet).max() < np.abs(full).max()


def test_mixer_start_stop_does_not_raise(state_with_audio_clip):
    state, _track_id = state_with_audio_clip
    mixer = AudioMixer(state)
    try:
        mixer.start()
    finally:
        mixer.stop()


def test_mixer_callback_advances_audio_time_without_ui_timer(state_with_audio_clip):
    state, _track_id = state_with_audio_clip
    mixer = AudioMixer(state, sample_rate=22050, channels=2, block_size=512)
    mixer.sync_playhead(1.0)
    state.is_playing = True

    out = np.zeros((512, 2), dtype=np.float32)
    mixer._callback(out, 512, None, None)

    assert mixer.audio_time == pytest.approx(1.0 + 512 / 22050)
    assert state.playhead == pytest.approx(mixer.audio_time)


def test_start_requests_high_latency_buffering_for_gil_contention_resilience(state_with_audio_clip, monkeypatch):
    """The real-time callback runs on a dedicated PortAudio thread but
    still competes for the GIL with the UI thread's per-frame video
    compositing. Requesting "high" latency gives the audio backend extra
    internal buffering slack so a brief GIL hold on the UI thread doesn't
    starve the callback and cause audible dropouts/stutter."""
    state, _track_id = state_with_audio_clip
    mixer = AudioMixer(state)
    captured_kwargs: dict = {}

    class _FakeStream:
        def __init__(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def close(self) -> None:
            pass

    import sounddevice as sd

    monkeypatch.setattr(sd, "OutputStream", _FakeStream)

    assert mixer.start() is True
    assert captured_kwargs.get("latency") == "high"
    mixer.stop()
