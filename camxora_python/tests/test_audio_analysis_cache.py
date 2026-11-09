"""Tests for persisted audio STFT analysis cache."""

from __future__ import annotations

import json
import math
import os
import struct
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from shared.services import audio_analysis_cache as cache_mod
from visualizer.audio import AudioAnalyzer


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


def test_cache_entry_is_compact_and_rebuilds_bands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    wav_path = tmp_path / "tone.wav"
    _write_test_wav(wav_path)

    analyzer = AudioAnalyzer(str(wav_path), fps=60, point_count=256)
    cache_mod.set_audio_analysis_cache(analyzer, str(wav_path))

    npz_files = list(tmp_path.glob("*.npz"))
    assert len(npz_files) == 1
    with np.load(npz_files[0], allow_pickle=False) as data:
        assert data["mag"].dtype == np.float16
        # Derived arrays stay out of the cache so entries stay small.
        for derived in ("freqs", "bass_idx", "mid_idx", "treble_idx"):
            assert derived not in data.files

    loaded = cache_mod.get_audio_analysis_cache(str(wav_path), fps=60, point_count=256)
    assert loaded is not None
    assert loaded._bass_idx.size > 0
    assert loaded._mid_idx.size > 0
    assert loaded._treble_idx.size > 0


def _write_fake_entry(directory: Path, stem: str, *, age_hours: float, size: int = 512) -> None:
    npz_path = directory / f"{stem}.npz"
    meta_path = directory / f"{stem}.meta.json"
    npz_path.write_bytes(b"\0" * size)
    meta_path.write_text(json.dumps({"version": cache_mod.CACHE_VERSION}), encoding="utf-8")
    stamp = time.time() - age_hours * 3600
    for path in (npz_path, meta_path):
        os.utime(path, (stamp, stamp))


def test_prune_removes_stale_versions_and_orphans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    (tmp_path / "old.npz").write_bytes(b"x")
    (tmp_path / "old.meta.json").write_text(json.dumps({"version": 3}), encoding="utf-8")
    (tmp_path / "orphan.npz").write_bytes(b"x")

    stats = cache_mod.prune_audio_analysis_cache()

    assert stats["deletedEntries"] == 2
    assert not (tmp_path / "old.npz").exists()
    assert not (tmp_path / "old.meta.json").exists()
    assert not (tmp_path / "orphan.npz").exists()


def test_prune_keeps_directory_under_size_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    _write_fake_entry(tmp_path, "newest", age_hours=1)
    _write_fake_entry(tmp_path, "middle", age_hours=5)
    _write_fake_entry(tmp_path, "oldest", age_hours=9)

    stats = cache_mod.prune_audio_analysis_cache(max_bytes=1200, max_age_days=365)

    assert stats["entries"] == 2
    assert not (tmp_path / "oldest.npz").exists()
    assert (tmp_path / "newest.npz").exists()
    assert (tmp_path / "middle.npz").exists()


def test_prune_removes_entries_past_retention(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    _write_fake_entry(tmp_path, "fresh", age_hours=1)
    _write_fake_entry(tmp_path, "stale", age_hours=24 * 40)

    stats = cache_mod.prune_audio_analysis_cache(max_bytes=1024 * 1024)

    assert stats["entries"] == 1
    assert (tmp_path / "fresh.npz").exists()
    assert not (tmp_path / "stale.npz").exists()
    assert not (tmp_path / "stale.meta.json").exists()


def test_clear_audio_analysis_cache_removes_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mod, "get_audio_analysis_cache_dir", lambda: tmp_path)
    _write_fake_entry(tmp_path, "one", age_hours=1)
    _write_fake_entry(tmp_path, "two", age_hours=2)

    stats = cache_mod.clear_audio_analysis_cache()

    assert stats["deletedEntries"] == 2
    assert list(tmp_path.glob("*")) == []
    assert cache_mod.audio_analysis_cache_stats()["entries"] == 0
