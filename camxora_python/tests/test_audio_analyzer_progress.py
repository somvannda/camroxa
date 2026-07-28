"""AudioAnalyzer progress + analysis sample-rate behavior."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from visualizer.audio import ANALYSIS_SAMPLE_RATE, AudioAnalyzer


def _write_test_wav(path: Path, *, duration_sec: float = 1.0, sample_rate: int = 44100) -> None:
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


def test_audio_analyzer_emits_progress_and_resamples(tmp_path: Path) -> None:
    wav_path = tmp_path / "tone.wav"
    _write_test_wav(wav_path)
    steps: list[str] = []

    analyzer = AudioAnalyzer(
        str(wav_path),
        fps=30,
        point_count=128,
        on_progress=steps.append,
    )

    assert analyzer.info.sample_rate == ANALYSIS_SAMPLE_RATE
    assert analyzer.info.duration_sec > 0.5
    assert any("Loading audio" in step for step in steps)
    assert any("spectrum" in step.lower() for step in steps)
    assert any("complete" in step.lower() for step in steps)


def test_frozen_beat_path_uses_onset_peaks(tmp_path: Path, monkeypatch) -> None:
    from visualizer import audio as audio_mod

    wav_path = tmp_path / "tone.wav"
    _write_test_wav(wav_path, duration_sec=1.5)
    monkeypatch.setattr(audio_mod, "_is_frozen", lambda: True)

    def _boom(*_a, **_k):
        raise AssertionError("librosa.beat.beat_track must not run when frozen")

    def _boom_stft(*_a, **_k):
        raise AssertionError("librosa.stft must not run when frozen")

    def _boom_peak_pick(*_a, **_k):
        raise AssertionError("librosa.util.peak_pick must not run when frozen")

    monkeypatch.setattr(audio_mod.librosa.beat, "beat_track", _boom)
    monkeypatch.setattr(audio_mod.librosa, "stft", _boom_stft)
    monkeypatch.setattr(audio_mod.librosa.util, "peak_pick", _boom_peak_pick)
    analyzer = AudioAnalyzer(str(wav_path), fps=30, point_count=64)
    assert analyzer.info.duration_sec > 1.0
    assert analyzer._mag.shape[0] > 0
    assert isinstance(analyzer.features_for_frame(0)["beat"], float)
