"""Decode full PCM for an audio-bearing asset (audio file, or a video's audio
track) into memory once on import.

Loading the whole waveform up front (rather than streaming) lets the
playback mixer (`audio/mixer.py`) and the visualizer's STFT precompute
sample it randomly/deterministically at any timeline position — the direct
analog of the reference app's `AnalyserNode`, but robust across scrubbing
and export instead of only "live while playing".
"""

from __future__ import annotations

import logging
import tempfile
import threading
import uuid
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from shared.lib.subprocess_utils import run_hidden
from studio.media.ffmpeg_utils import get_ffmpeg_exe

logger = logging.getLogger(__name__)

DEFAULT_VIZ_BANDS = 24
DEFAULT_VIZ_N_FFT = 2048
DEFAULT_VIZ_HOP = 1024


class AudioSource:
    def __init__(self, samples: np.ndarray, sample_rate: int) -> None:
        """`samples` is float32, shape (n_frames, n_channels)."""
        self.samples = samples
        self.sample_rate = sample_rate
        self.mono = samples.mean(axis=1).astype(np.float32) if samples.ndim == 2 else samples
        self._band_grid: np.ndarray | None = None
        self._band_hop_seconds = 0.0
        self._band_count_cached = 0
        self._mono_resampled: dict[int, np.ndarray] = {}

    @property
    def duration(self) -> float:
        return len(self.mono) / self.sample_rate if self.sample_rate else 0.0

    def _ensure_bands(
        self, n_bands: int = DEFAULT_VIZ_BANDS, n_fft: int = DEFAULT_VIZ_N_FFT, hop_length: int = DEFAULT_VIZ_HOP
    ) -> None:
        """Precompute a deterministic STFT magnitude grid, grouped into
        `n_bands` logarithmically-spaced bands and normalized to 0..1 — the
        analog of the reference app's live `AnalyserNode`, but computed once
        so any timeline position (scrub, export) samples the same values."""
        if self._band_grid is not None and self._band_count_cached == n_bands:
            return
        if len(self.mono) == 0:
            self._band_grid = np.zeros((1, n_bands), dtype=np.float32)
            self._band_hop_seconds = hop_length / max(1, self.sample_rate)
            self._band_count_cached = n_bands
            return

        signal = self.mono
        if len(signal) < n_fft:
            signal = np.pad(signal, (0, n_fft - len(signal)))

        stft = librosa.stft(signal, n_fft=n_fft, hop_length=hop_length)
        magnitude = np.abs(stft)  # shape (n_freq_bins, n_frames)
        n_freq_bins, n_frames = magnitude.shape

        edges = np.unique(np.geomspace(1, n_freq_bins, n_bands + 1).astype(int))
        edges = np.clip(edges, 0, n_freq_bins)
        if len(edges) < n_bands + 1:
            edges = np.linspace(0, n_freq_bins, n_bands + 1).astype(int)

        bands = np.zeros((n_frames, n_bands), dtype=np.float32)
        for i in range(n_bands):
            lo, hi = int(edges[i]), max(int(edges[i]) + 1, int(edges[i + 1]))
            bands[:, i] = magnitude[lo:hi, :].mean(axis=0)

        bands = np.log1p(bands)
        max_val = float(bands.max()) if bands.size else 0.0
        if max_val > 0:
            bands = bands / max_val

        self._band_grid = bands
        self._band_hop_seconds = hop_length / self.sample_rate
        self._band_count_cached = n_bands

    def get_spectrum_bands(self, time: float, n_bands: int = DEFAULT_VIZ_BANDS) -> np.ndarray:
        """Nearest-frame lookup into the precomputed STFT band grid."""
        self._ensure_bands(n_bands)
        grid = self._band_grid
        if grid is None or len(grid) == 0 or self._band_hop_seconds <= 0:
            return np.zeros(n_bands, dtype=np.float32)
        idx = int(round(max(0.0, time) / self._band_hop_seconds))
        idx = max(0, min(len(grid) - 1, idx))
        return grid[idx]

    def get_waveform_samples(self, time: float, window: float = 0.05, count: int = 48) -> np.ndarray:
        """A small, evenly-spaced sample of the raw waveform around `time` —
        used by the "Waveform" visualizer style."""
        raw = self.slice_seconds(time - window / 2, window)
        if len(raw) == 0:
            return np.zeros(count, dtype=np.float32)
        idx = np.linspace(0, len(raw) - 1, count).astype(int)
        return raw[idx]

    def get_amplitude_envelope(self, start: float, length: float, bars: int) -> np.ndarray:
        """Peak amplitude of `bars` evenly-spaced sub-segments across
        [start, start+length) — a cheap "static overview" shape for drawing
        a whole clip's real waveform on the timeline (unlike
        `get_waveform_samples`, which centers on a live-scrubbing window),
        normalized to 0..1 so it draws consistently regardless of the
        source's loudness."""
        if bars <= 0:
            return np.zeros(0, dtype=np.float32)
        if length <= 0:
            return np.zeros(bars, dtype=np.float32)
        seg_len = length / bars
        out = np.zeros(bars, dtype=np.float32)
        for i in range(bars):
            seg = self.slice_seconds(start + i * seg_len, seg_len)
            out[i] = float(np.abs(seg).max()) if len(seg) else 0.0
        max_val = float(out.max()) if out.size else 0.0
        if max_val > 0:
            out = out / max_val
        return out

    def slice_seconds(self, start: float, length: float) -> np.ndarray:
        """Return a mono float32 slice [start, start+length), zero-padded at
        the boundaries — used for live audio-mix playback and STFT lookups."""
        return self._slice_mono(self.mono, self.sample_rate, start, length)

    def slice_seconds_at_rate(self, start: float, length: float, target_sr: int) -> np.ndarray:
        """Like `slice_seconds`, but returns samples at `target_sr` so the
        real-time mixer never has to resample every output block."""
        if target_sr <= 0:
            return np.zeros(0, dtype=np.float32)
        if target_sr == self.sample_rate:
            return self.slice_seconds(start, length)
        mono = self._mono_at_sample_rate(target_sr)
        return self._slice_mono(mono, target_sr, start, length)

    def _mono_at_sample_rate(self, target_sr: int) -> np.ndarray:
        cached = self._mono_resampled.get(target_sr)
        if cached is not None:
            return cached
        if self.sample_rate <= 0 or len(self.mono) == 0:
            out = np.zeros(0, dtype=np.float32)
        elif target_sr == self.sample_rate:
            out = self.mono
        else:
            target_len = max(1, int(round(len(self.mono) * target_sr / self.sample_rate)))
            x_old = np.linspace(0.0, 1.0, len(self.mono), endpoint=False)
            x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
            out = np.interp(x_new, x_old, self.mono).astype(np.float32)
        self._mono_resampled[target_sr] = out
        return out

    @staticmethod
    def _slice_mono(mono: np.ndarray, sample_rate: int, start: float, length: float) -> np.ndarray:
        if sample_rate <= 0:
            return np.zeros(0, dtype=np.float32)
        start_idx = int(round(start * sample_rate))
        n = int(round(length * sample_rate))
        end_idx = start_idx + n
        out = np.zeros(n, dtype=np.float32)
        src_start = max(0, start_idx)
        src_end = min(len(mono), end_idx)
        if src_start < src_end:
            dst_start = src_start - start_idx
            out[dst_start : dst_start + (src_end - src_start)] = mono[src_start:src_end]
        return out


def _extract_video_audio_wav(path: Path, cache_dir: Path) -> Path | None:
    ffmpeg_exe = get_ffmpeg_exe()
    out_path = cache_dir / f"audio_{uuid.uuid4().hex[:9]}.wav"
    try:
        result = run_hidden(
            [
                ffmpeg_exe, "-y", "-i", str(path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100",
                str(out_path),
            ],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0 or not out_path.exists():
            return None
        return out_path
    except Exception:
        logger.exception("Failed to extract audio track from %s", path)
        return None


def load_audio_source(path: str | Path, media_type: str, cache_dir: Path | None = None) -> AudioSource | None:
    path = Path(path)
    if media_type == "image":
        return None

    if media_type == "audio":
        try:
            data, sr = sf.read(str(path), dtype="float32", always_2d=True)
        except Exception:
            logger.exception("Failed to decode audio file %s", path)
            return None
        return AudioSource(data, sr)

    if media_type == "video":
        cache_dir = cache_dir or Path(tempfile.gettempdir()) / "camxora_studio_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        wav_path = _extract_video_audio_wav(path, cache_dir)
        if wav_path is None:
            return None
        try:
            data, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
        except Exception:
            logger.exception("Failed to decode extracted audio for %s", path)
            return None
        return AudioSource(data, sr)

    return None


class AudioSourceCache:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir
        self._sources: dict[str, AudioSource | None] = {}
        self._lock = threading.Lock()

    def get(self, media_id: str, path: str, media_type: str) -> AudioSource | None:
        with self._lock:
            cached = self._sources.get(media_id)
            if cached is not None or media_id in self._sources:
                return cached

        source = load_audio_source(path, media_type, self._cache_dir)

        with self._lock:
            if media_id not in self._sources:
                self._sources[media_id] = source
            return self._sources[media_id]

    def release_all(self) -> None:
        with self._lock:
            self._sources.clear()
