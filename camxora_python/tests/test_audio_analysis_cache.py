"""Tests for persisted audio STFT analysis cache."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from shared.services import audio_analysis_cache as cache_mod
from visualizer_video.audio import AudioAnalyzer


def _write_test_wav(path: Path, *, duration_sec: float = 0.75, sample_rate: int = 22050) -> None:
    frame_count = int(duration_sec * sample_rate)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            sample = int(32767 * math.sin(2 * math.pi * 440.0 * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        handle.writeframes(frames)


def test_audio_analysis_cache_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    wav_path = tmp_path / "tone.wav"
    _write_test_wav(wav_path)

    original = AudioAnalyzer(str(wav_path), fps=60, point_count=256)
    cache_mod.set_audio_analysis_cache(original, str(wav_path))

    loaded = cache_mod.get_audio_analysis_cache(str(wav_path), fps=60, point_count=256)
    assert loaded is not None
    assert loaded.info.duration_sec == pytest.approx(original.info.duration_sec, rel=0.05)
    assert loaded.fft_for_frame(0).shape == original.fft_for_frame(0).shape
    assert loaded.features_for_frame(0)["energy"] >= 0.0


def test_audio_analysis_cache_miss_on_settings_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    wav_path = tmp_path / "tone.wav"
    _write_test_wav(wav_path)

    analyzer = AudioAnalyzer(str(wav_path), fps=60, point_count=256)
    cache_mod.set_audio_analysis_cache(analyzer, str(wav_path))

    assert cache_mod.get_audio_analysis_cache(str(wav_path), fps=30, point_count=256) is None


def test_audio_analysis_cache_invalidated_on_file_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    wav_path = tmp_path / "tone.wav"
    _write_test_wav(wav_path, duration_sec=0.5)

    analyzer = AudioAnalyzer(str(wav_path), fps=60, point_count=128)
    cache_mod.set_audio_analysis_cache(analyzer, str(wav_path))
    assert cache_mod.get_audio_analysis_cache(str(wav_path), fps=60, point_count=128) is not None

    _write_test_wav(wav_path, duration_sec=1.0)
    assert cache_mod.get_audio_analysis_cache(str(wav_path), fps=60, point_count=128) is None


def test_load_audio_analyzer_reports_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    wav_path = tmp_path / "tone.wav"
    _write_test_wav(wav_path)

    _, first_hit = cache_mod.load_audio_analyzer(str(wav_path), fps=60, point_count=128, use_cache=True)
    assert first_hit is False
    _, second_hit = cache_mod.load_audio_analyzer(str(wav_path), fps=60, point_count=128, use_cache=True)
    assert second_hit is True
