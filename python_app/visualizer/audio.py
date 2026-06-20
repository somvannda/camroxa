from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass(frozen=True)
class AudioInfo:
    sample_rate: int
    duration_sec: float
    frames: int


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
            _tempo, beat_frames = librosa.beat.beat_track(y=y, sr=self._sr, hop_length=self._hop_length, units="frames")
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
