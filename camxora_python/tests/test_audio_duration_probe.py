"""Tests for fast audio duration probing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from visualizer.audio import probe_audio_duration_sec


def test_probe_audio_duration_sec_reads_wav_metadata(tmp_path: Path) -> None:
    path = tmp_path / "probe.wav"
    sr = 22050
    seconds = 1.5
    samples = np.zeros(int(sr * seconds), dtype=np.float32)
    sf.write(str(path), samples, sr)

    duration = probe_audio_duration_sec(str(path))
    assert duration == pytest.approx(seconds, abs=0.05)


def test_probe_audio_duration_sec_missing_file() -> None:
    assert probe_audio_duration_sec("") == 0.0
    assert probe_audio_duration_sec("C:/does/not/exist.mp3") == 0.0
