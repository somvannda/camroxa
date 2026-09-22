from pathlib import Path

import numpy as np
import pytest

from studio.media.audio_source import AudioSource, load_audio_source


def test_load_audio_source_from_audio_file(sample_audio: Path, tmp_path: Path):
    source = load_audio_source(sample_audio, "audio", cache_dir=tmp_path)
    assert source is not None
    assert source.sample_rate == 22050
    assert source.duration == pytest.approx(1.5, rel=0.02)


def test_load_audio_source_video_without_audio_track_returns_none(sample_video: Path, tmp_path: Path):
    source = load_audio_source(sample_video, "video", cache_dir=tmp_path)
    assert source is None


def test_load_audio_source_image_returns_none(sample_image: Path, tmp_path: Path):
    source = load_audio_source(sample_image, "image", cache_dir=tmp_path)
    assert source is None


def test_get_spectrum_bands_returns_normalized_values(sample_audio: Path, tmp_path: Path):
    source = load_audio_source(sample_audio, "audio", cache_dir=tmp_path)
    assert source is not None
    bands = source.get_spectrum_bands(0.5, n_bands=16)
    assert bands.shape == (16,)
    assert bands.min() >= 0.0
    assert bands.max() <= 1.0 + 1e-6
    assert bands.max() > 0.0  # our fixture has a real 440Hz tone, not silence


def test_get_spectrum_bands_clamps_out_of_range_time(sample_audio: Path, tmp_path: Path):
    source = load_audio_source(sample_audio, "audio", cache_dir=tmp_path)
    assert source is not None
    bands_far = source.get_spectrum_bands(1000.0, n_bands=8)
    assert bands_far.shape == (8,)


def test_get_waveform_samples_returns_requested_count(sample_audio: Path, tmp_path: Path):
    source = load_audio_source(sample_audio, "audio", cache_dir=tmp_path)
    assert source is not None
    samples = source.get_waveform_samples(0.5, window=0.05, count=32)
    assert samples.shape == (32,)


def test_get_amplitude_envelope_returns_requested_bar_count_normalized(sample_audio: Path, tmp_path: Path):
    source = load_audio_source(sample_audio, "audio", cache_dir=tmp_path)
    assert source is not None
    envelope = source.get_amplitude_envelope(0.0, 1.5, bars=24)
    assert envelope.shape == (24,)
    assert envelope.min() >= 0.0
    assert envelope.max() == pytest.approx(1.0)  # normalized so the loudest bar is 1.0


def test_get_amplitude_envelope_zero_length_returns_zeros():
    sr = 100
    samples = np.ones((100, 1), dtype=np.float32)
    source = AudioSource(samples, sr)
    envelope = source.get_amplitude_envelope(0.0, 0.0, bars=10)
    assert envelope.shape == (10,)
    assert np.all(envelope == 0.0)


def test_get_amplitude_envelope_silence_returns_all_zeros():
    sr = 100
    samples = np.zeros((300, 1), dtype=np.float32)
    source = AudioSource(samples, sr)
    envelope = source.get_amplitude_envelope(0.0, 3.0, bars=6)
    assert np.all(envelope == 0.0)


def test_slice_seconds_exact_length_and_zero_padding():
    sr = 100
    samples = np.ones((300, 1), dtype=np.float32)  # 3s mono @ 100Hz
    source = AudioSource(samples, sr)

    middle = source.slice_seconds(1.0, 0.5)
    assert len(middle) == 50
    assert np.all(middle == 1.0)

    # slice that runs past the end should be zero-padded
    tail = source.slice_seconds(2.8, 0.5)
    assert len(tail) == 50
    assert np.all(tail[:20] == 1.0)
    assert np.all(tail[20:] == 0.0)

    # slice entirely before start (negative) should be all zeros where out of range
    head = source.slice_seconds(-0.2, 0.4)
    assert len(head) == 40
    assert np.all(head[:20] == 0.0)


def test_slice_seconds_at_rate_resamples_once_and_matches_duration():
    sr = 100
    samples = np.ones((300, 1), dtype=np.float32)  # 3s @ 100Hz
    source = AudioSource(samples, sr)

    block = source.slice_seconds_at_rate(0.5, 0.25, target_sr=200)
    assert len(block) == 50  # 0.25s @ 200Hz

    # Cached resample path should return identical slices.
    again = source.slice_seconds_at_rate(0.5, 0.25, target_sr=200)
    assert np.array_equal(block, again)
