"""Decode misnamed containers without calling playable audio 'fake' or hanging librosa."""

from __future__ import annotations

import struct
import time
from pathlib import Path

import numpy as np
import pytest

from visualizer import audio as audio_mod
from visualizer.audio import sniff_audio_container


def _write(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def _ftyp(brand: bytes) -> bytes:
    compatible = brand + b"isom"
    body = b"ftyp" + brand + b"\x00\x00\x00\x00" + compatible
    return struct.pack(">I", 8 + len(body)) + body


def test_sniff_iso_bmff_even_when_named_mp3(tmp_path: Path) -> None:
    path = _write(tmp_path / "song_OK.mp3", _ftyp(b"isom") + b"\x00" * 300)
    assert sniff_audio_container(str(path)) == "iso_bmff"


@pytest.mark.parametrize("brand", [b"isom", b"iso2", b"mp42", b"M4A "])
def test_sniff_ftyp_brands_are_iso_bmff(tmp_path: Path, brand: bytes) -> None:
    path = _write(tmp_path / "song_OK.mp3", _ftyp(brand) + b"\x00" * 300)
    assert sniff_audio_container(str(path)) == "iso_bmff"


@pytest.mark.parametrize(
    ("payload", "kind"),
    [
        (b"ID3\x04\x00\x00" + b"\x00" * 300, "mpeg"),
        (b"\xff\xfb" + b"\x00" * 300, "mpeg"),
        (b"RIFF" + b"\x00\x00\x00\x00WAVE" + b"\x00" * 300, "wav"),
        (b"OggS" + b"\x00" * 300, "ogg"),
        (b"fLaC" + b"\x00" * 300, "flac"),
        (b"\x1aE\xdf\xa3" + b"\x00" * 300, "webm"),
        (b"\xff\xf1" + b"\x00" * 300, "aac_adts"),
        (b"mp3", "too_small"),
    ],
)
def test_sniff_known_magic(tmp_path: Path, payload: bytes, kind: str) -> None:
    path = _write(tmp_path / "song_OK.mp3", payload)
    assert sniff_audio_container(str(path)) == kind


def test_too_small_fails_before_librosa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write(tmp_path / "stub.mp3", b"mp3")

    def boom(*_a, **_k):
        raise AssertionError("decoders must not run on tiny stubs")

    monkeypatch.setattr(audio_mod, "_load_via_ffmpeg", boom)
    monkeypatch.setattr(audio_mod, "_load_via_librosa", boom)
    with pytest.raises(RuntimeError, match="too small"):
        audio_mod._load_mono_waveform(str(path), target_sr=22050)


@pytest.mark.parametrize("kind_payload", [_ftyp(b"isom") + b"\x00" * 300, b"\x1aE\xdf\xa3" + b"\x00" * 300])
def test_ffmpeg_first_containers_skip_librosa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind_payload: bytes
) -> None:
    path = _write(tmp_path / "song_OK.mp3", kind_payload)
    called = {"librosa": False}

    def fake_ffmpeg(path_text: str, *, target_sr: int, timeout_sec: float = 90.0) -> np.ndarray:
        return np.zeros(int(target_sr) * 2, dtype=np.float32)

    def fake_librosa(*_a, **_k):
        called["librosa"] = True
        raise AssertionError("librosa must not run for ffmpeg-first containers")

    monkeypatch.setattr(audio_mod, "_load_via_ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(audio_mod, "_load_via_librosa", fake_librosa)
    _y, sr, backend = audio_mod._load_mono_waveform(str(path), target_sr=22050)
    assert backend == "ffmpeg"
    assert sr == 22050
    assert called["librosa"] is False


def test_iso_bmff_duration_uses_ffprobe_not_librosa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(tmp_path / "song_OK.mp3", _ftyp(b"isom") + b"\x00" * 300)

    def boom(*_a, **_k):
        raise AssertionError("librosa.get_duration must not run for ISO-BMFF")

    monkeypatch.setattr(audio_mod, "_ffprobe_duration_sec", lambda _p: 152.44)
    monkeypatch.setattr(audio_mod.librosa, "get_duration", boom)
    assert audio_mod.probe_audio_duration_sec(str(path)) == pytest.approx(152.44)


def test_librosa_fallback_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(*_a, **_k):
        time.sleep(5)
        return np.zeros(8, dtype=np.float32), 22050

    monkeypatch.setattr(audio_mod.librosa, "load", hang)
    with pytest.raises(RuntimeError, match="timed out"):
        audio_mod._load_via_librosa("missing.mp3", target_sr=22050, timeout_sec=0.2)


_LIBRARY_OPUS_MP3S = [
    Path(r"F:\Suno\bass-ignition\2026-08-19_Voltage-Hinterland-Clash\8. Chase Spotlight Under Pressure_OK.mp3"),
    Path(r"F:\Suno\bass-ignition\2026-08-18_Arcade-Dawn-Rage\13. Sunline Breaks Horizon_OK.mp3"),
    Path(r"F:\Suno\bass-reactor\2026-08-19_Echoes-Through-Dimming-Wires\8. Chase Spotlight Under Pressure_Alt.mp3"),
    Path(r"F:\Suno\bass-reactor\2026-08-18_Neon-Highway-Reverie\13. Sunline Breaks Horizon_Alt.mp3"),
]


@pytest.mark.parametrize("path", _LIBRARY_OPUS_MP3S, ids=lambda p: p.name)
def test_library_opus_mp3s_are_real_audio_decoded_by_ffmpeg(path: Path) -> None:
    if not path.is_file():
        pytest.skip(f"library file not on this machine: {path}")
    assert sniff_audio_container(str(path)) == "iso_bmff"
    y, sr, backend = audio_mod._load_mono_waveform(str(path), target_sr=22050)
    assert backend == "ffmpeg"
    assert sr == 22050
    assert len(y) > 22050 * 100
