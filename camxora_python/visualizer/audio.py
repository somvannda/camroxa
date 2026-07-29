from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import librosa
import numpy as np

# Fixed analysis rate — native 44.1/48 kHz makes STFT/beat_track extremely heavy
# on dual-socket Xeon boxes (OpenBLAS oversubscription → appears hung forever).
ANALYSIS_SAMPLE_RATE = 22050
_BLAS_THREAD_CAP = 4

ProgressCallback = Callable[[str], None]


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


@contextmanager
def _blas_thread_limit(n: int = _BLAS_THREAD_CAP) -> Iterator[None]:
    """Cap OpenBLAS/MKL/OMP threads so dual-Xeon machines do not livelock STFT."""
    keys = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    )
    prior = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ[key] = str(max(1, int(n)))
    try:
        try:
            from threadpoolctl import threadpool_limits

            with threadpool_limits(limits=max(1, int(n))):
                yield
        except Exception:
            yield
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class AudioAnalyzer:
    def __init__(
        self,
        mp3_path: str,
        fps: int,
        point_count: int,
        n_fft: int = 2048,
        *,
        on_progress: ProgressCallback | None = None,
        analysis_sr: int = ANALYSIS_SAMPLE_RATE,
    ) -> None:
        def _progress(message: str) -> None:
            if on_progress is not None:
                on_progress(message)

        with _blas_thread_limit():
            _progress("Loading audio…")
            y, sr = librosa.load(
                mp3_path,
                sr=int(max(8000, int(analysis_sr))),
                mono=True,
            )
            if y is None or sr is None:
                raise RuntimeError("Could not load audio")
            self._sr = int(sr)
            self._fps = int(fps)
            self._point_count = int(point_count)
            self._n_fft = int(n_fft)
            self._hop_length = max(1, int(round(self._sr / max(1, self._fps))))
            self._analyze_waveform(y, on_progress=_progress)

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
        inst._fft_out = np.zeros(inst._point_count, dtype=np.float32)
        inst._feat_cache_idx = -1
        inst._feat_cache: dict = {}
        return inst

    def _analyze_waveform(self, y: np.ndarray, *, on_progress: ProgressCallback | None = None) -> None:
        def _progress(message: str) -> None:
            if on_progress is not None:
                on_progress(message)

        _progress("Computing spectrum…")
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
        self._fft_out = np.zeros(self._point_count, dtype=np.float32)
        self._feat_cache_idx = -1
        self._feat_cache: dict = {}

        _progress("Detecting onset…")
        onset_env = librosa.onset.onset_strength(y=y, sr=self._sr, hop_length=self._hop_length)
        onset_env = onset_env.astype(np.float32)
        if onset_env.size:
            onset_env = onset_env / max(1e-9, float(np.max(onset_env)))
        self._onset_env = onset_env

        _progress("Detecting beats…")
        try:
            # Reuse onset envelope — avoids a second full spectrogram pass.
            _tempo, beat_frames = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=self._sr,
                hop_length=self._hop_length,
                units="frames",
            )
            beat_set = {int(x) for x in np.asarray(beat_frames).reshape(-1).tolist()}
        except Exception:
            beat_set = set()
        self._beat_set = beat_set
        _progress("Audio analysis complete")

    @property
    def point_count(self) -> int:
        return self._point_count

    @point_count.setter
    def point_count(self, val: int) -> None:
        self._point_count = int(val)
        self._x_out = np.linspace(0.0, 1.0, num=self._point_count, dtype=np.float32)
        self._fft_out = np.zeros(self._point_count, dtype=np.float32)
        self._feat_cache_idx = -1

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def info(self) -> AudioInfo:
        return self._info

    def fft_for_frame(self, frame_index: int) -> np.ndarray:
        idx = min(max(0, int(frame_index)), max(0, self._frames_bins - 1))
        col = self._mag[:, idx]
        # Reuse output buffer — avoids a new allocation every paint frame (GC hitch).
        out = getattr(self, "_fft_out", None)
        if out is None or int(out.shape[0]) != int(self._point_count):
            self._fft_out = np.zeros(self._point_count, dtype=np.float32)
            out = self._fft_out
        out[:] = np.interp(self._x_out, self._x_in, col)
        np.clip(out, 0.0, 1.0, out=out)
        return out

    def features_for_frame(self, frame_index: int) -> dict:
        idx = min(max(0, int(frame_index)), max(0, self._frames_bins - 1))
        if int(getattr(self, "_feat_cache_idx", -1)) == idx and getattr(self, "_feat_cache", None):
            return self._feat_cache
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

        self._feat_cache = {
            "bass": bass,
            "mid": mid,
            "treble": treble,
            "energy": energy,
            "onset": onset,
            "beat": beat,
        }
        self._feat_cache_idx = idx
        return self._feat_cache
