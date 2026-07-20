from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np


@dataclass(frozen=True)
class AudioInfo:
    sample_rate: int
    duration_sec: float
    frames: int


def probe_audio_duration_sec(path: str) -> float:
    """Fast duration probe without building the full STFT analyzer.

    Used so first-play transport (seek bar / total time) works before FFT analysis
    finishes. Prefer soundfile metadata; fall back to librosa path duration.
    """
    text = str(path or "").strip()
    if not text or not Path(text).is_file():
        return 0.0
    try:
        import soundfile as sf

        info = sf.info(text)
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if duration > 0:
            return duration
    except Exception:
        pass
    try:
        duration = float(librosa.get_duration(path=text))
        return max(0.0, duration)
    except Exception:
        return 0.0


class AudioAnalyzer:
    def __init__(self, mp3_path: str, fps: int, point_count: int, n_fft: int = 2048) -> None:
        y, sr = librosa.load(mp3_path, sr=None, mono=True)
        if y is None or sr is None:
            raise RuntimeError("Could not load audio")
        self._sr = int(sr)
        self._fps = int(fps)
        self._point_count = int(point_count)
        self._n_fft = int(n_fft)
        self._hop_length = max(1, int(round(self._sr / max(1, self._fps))))
        self._analyze_waveform(y)

    @classmethod
    def from_cached_arrays(
        cls,
        *,
        fps: int,
        point_count: int,
        n_fft: int,
        sample_rate: int,
        hop_length: int,
        duration_sec: float,
        mag: np.ndarray,
        freqs: np.ndarray,
        bass_idx: np.ndarray,
        mid_idx: np.ndarray,
        treble_idx: np.ndarray,
        onset_env: np.ndarray,
        beat_frames: np.ndarray,
    ) -> AudioAnalyzer:
        inst = cls.__new__(cls)
        inst._sr = int(sample_rate)
        inst._fps = int(fps)
        inst._point_count = int(point_count)
        inst._n_fft = int(n_fft)
        inst._hop_length = int(hop_length)
        inst._mag = np.asarray(mag, dtype=np.float32)
        inst._freqs = np.asarray(freqs, dtype=np.float32)
        inst._bass_idx = np.asarray(bass_idx)
        inst._mid_idx = np.asarray(mid_idx)
        inst._treble_idx = np.asarray(treble_idx)
        inst._onset_env = np.asarray(onset_env, dtype=np.float32)
        inst._beat_set = {int(x) for x in np.asarray(beat_frames).tolist()}
        duration = float(duration_sec)
        frames = int(np.ceil(duration * inst._fps))
        inst._info = AudioInfo(sample_rate=inst._sr, duration_sec=duration, frames=frames)
        inst._freq_bins = int(inst._mag.shape[0])
        inst._frames_bins = int(inst._mag.shape[1])
        inst._x_in = np.linspace(0.0, 1.0, num=inst._freq_bins, dtype=np.float32)
        inst._x_out = np.linspace(0.0, 1.0, num=inst._point_count, dtype=np.float32)
        return inst

    def _analyze_waveform(self, y: np.ndarray) -> None:
        stft = librosa.stft(y, n_fft=self._n_fft, hop_length=self._hop_length, window="hann", center=True)
        mag = np.abs(stft).astype(np.float32)
        mag_max = float(np.max(mag)) if mag.size else 1.0
        self._mag = mag / max(1e-9, mag_max)

        freqs = librosa.fft_frequencies(sr=self._sr, n_fft=self._n_fft).astype(np.float32)
        self._freqs = freqs
        self._bass_idx = np.where((freqs >= 20.0) & (freqs < 200.0))[0]
        self._mid_idx = np.where((freqs >= 200.0) & (freqs < 2000.0))[0]
        self._treble_idx = np.where((freqs >= 2000.0) & (freqs < 8000.0))[0]

        duration = float(librosa.get_duration(y=y, sr=self._sr))
        frames = int(np.ceil(duration * self._fps))
        self._info = AudioInfo(sample_rate=self._sr, duration_sec=duration, frames=frames)

        self._freq_bins = self._mag.shape[0]
        self._frames_bins = self._mag.shape[1]
        self._x_in = np.linspace(0.0, 1.0, num=self._freq_bins, dtype=np.float32)
        self._x_out = np.linspace(0.0, 1.0, num=self._point_count, dtype=np.float32)

        onset_env = librosa.onset.onset_strength(y=y, sr=self._sr, hop_length=self._hop_length)
        onset_env = onset_env.astype(np.float32)
        if onset_env.size:
            onset_env = onset_env / max(1e-9, float(np.max(onset_env)))
        self._onset_env = onset_env

        try:
            _tempo, beat_frames = librosa.beat.beat_track(
                y=y, sr=self._sr, hop_length=self._hop_length, units="frames"
            )
            beat_set = set(int(x) for x in beat_frames.tolist())
        except Exception:
            beat_set = set()
        self._beat_set = beat_set

    @property
    def point_count(self) -> int:
        return self._point_count

    @point_count.setter
    def point_count(self, val: int) -> None:
        self._point_count = int(val)
        self._x_out = np.linspace(0.0, 1.0, num=self._point_count, dtype=np.float32)

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def info(self) -> AudioInfo:
        return self._info

    def fft_for_frame(self, frame_index: int) -> np.ndarray:
        idx = min(max(0, int(frame_index)), max(0, self._frames_bins - 1))
        col = self._mag[:, idx]
        out = np.interp(self._x_out, self._x_in, col).astype(np.float32)
        out = np.clip(out, 0.0, 1.0)
        return out

    def features_for_frame(self, frame_index: int) -> dict:
        idx = min(max(0, int(frame_index)), max(0, self._frames_bins - 1))
        col = self._mag[:, idx]

        def mean_or_zero(indices: np.ndarray) -> float:
            if indices.size == 0:
                return 0.0
            return float(np.mean(col[indices]))

        bass = mean_or_zero(self._bass_idx)
        mid = mean_or_zero(self._mid_idx)
        treble = mean_or_zero(self._treble_idx)
        energy = float(np.mean(col)) if col.size else 0.0

        onset_idx = min(max(0, idx), max(0, self._onset_env.size - 1))
        onset = float(self._onset_env[onset_idx]) if self._onset_env.size else 0.0
        beat = 1.0 if idx in self._beat_set else 0.0

        return {
            "bass": bass,
            "mid": mid,
            "treble": treble,
            "energy": energy,
            "onset": onset,
            "beat": beat,
        }
