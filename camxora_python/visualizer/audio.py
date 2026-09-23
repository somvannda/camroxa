from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal

# Cap BLAS before numpy/librosa load OpenBLAS (env alone is not enough later).
_BLAS_THREAD_CAP = 1 if bool(getattr(sys, "frozen", False)) else 4
for _blas_key in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_blas_key, str(_BLAS_THREAD_CAP))

import librosa
import numpy as np

from shared.lib.subprocess_utils import run_hidden  # noqa: E402

# Fixed analysis rate — native 44.1/48 kHz makes STFT/beat_track extremely heavy
# on dual-socket Xeon boxes (OpenBLAS oversubscription → appears hung forever).
ANALYSIS_SAMPLE_RATE = 22050
FFMPEG_DECODE_TIMEOUT_SEC = 90.0
LIBROSA_LOAD_TIMEOUT_SEC = 45.0

AudioContainerKind = Literal[
    "mpeg",
    "iso_bmff",
    "wav",
    "ogg",
    "flac",
    "webm",
    "aac_adts",
    "too_small",
    "unknown",
]

# mpg123 / librosa-audioread can hang or mis-read these even when a player works.
_FFMPEG_FIRST_CONTAINERS = frozenset({"iso_bmff", "webm", "aac_adts"})
_MIN_AUDIO_BYTES = 256

ProgressCallback = Callable[[str], None]


def sniff_audio_container(path: str) -> AudioContainerKind:
    """Classify the on-disk container from magic bytes, ignoring the file extension.

    Suno (and some CDNs) sometimes deliver Opus/AAC inside an MP4/M4A body
    saved as ``.mp3``. Windows will still play that file; mpg123/soundfile will
    not, and librosa/audioread can hang indefinitely on it.
    """
    text = str(path or "").strip()
    if not text:
        return "unknown"
    try:
        size = Path(text).stat().st_size
        with Path(text).open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return "unknown"
    if size < _MIN_AUDIO_BYTES or len(head) < 8:
        return "too_small"
    if head[4:8] == b"ftyp":
        return "iso_bmff"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"OggS":
        return "ogg"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if head[:3] == b"ID3":
        return "mpeg"
    # AAC ADTS uses 12-bit 0xFFF sync; MP3 frames are typically 0xFFEx (not 0xFFF0+).
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xF6) == 0xF0:
        return "aac_adts"
    if head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "mpeg"
    return "unknown"


@dataclass(frozen=True)
class AudioInfo:
    sample_rate: int
    duration_sec: float
    frames: int


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _audio_diag(message: str) -> None:
    """Always-flush diagnostics for installer hangs (also prints for MG_EVENT capture)."""
    text = str(message or "").strip()
    if not text:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {text}"
    try:
        print(f"[audio-diag] {text}", flush=True)
    except Exception:
        pass
    try:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        path = base / "Camxora" / "logs" / "audio-load-diag.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        pass


def _probe_decode_backends() -> str:
    bits: list[str] = [f"frozen={_is_frozen()}"]
    try:
        import soundfile as sf

        bits.append(f"soundfile={getattr(sf, '__file__', '?')}")
        try:
            import _soundfile_data

            bits.append(f"_soundfile_data={getattr(_soundfile_data, '__file__', '?')}")
        except Exception as exc:
            bits.append(f"_soundfile_data=ERR:{type(exc).__name__}:{exc}")
    except Exception as exc:
        bits.append(f"soundfile=ERR:{type(exc).__name__}:{exc}")
    try:
        import audioread

        bits.append(f"audioread={getattr(audioread, '__file__', '?')}")
    except Exception as exc:
        bits.append(f"audioread=ERR:{type(exc).__name__}:{exc}")
    try:
        import threadpoolctl

        bits.append(f"threadpoolctl={getattr(threadpoolctl, '__file__', '?')}")
    except Exception as exc:
        bits.append(f"threadpoolctl=ERR:{type(exc).__name__}:{exc}")
    bits.append(f"librosa={getattr(librosa, '__file__', '?')}")
    return " | ".join(bits)


def _resample_mono(y: np.ndarray, *, orig_sr: int, target_sr: int) -> tuple[np.ndarray, str]:
    """Resample mono float32. Prefer soxr (fast); avoid hung librosa/numba in frozen builds."""
    if int(orig_sr) == int(target_sr):
        return np.asarray(y, dtype=np.float32), "none"
    mono = np.asarray(y, dtype=np.float32).reshape(-1)
    try:
        import soxr

        out = soxr.resample(mono, int(orig_sr), int(target_sr))
        return np.asarray(out, dtype=np.float32).reshape(-1), "soxr"
    except Exception as exc:
        _audio_diag(f"soxr resample failed: {type(exc).__name__}: {exc}")
    try:
        from math import gcd

        from scipy import signal

        g = gcd(int(orig_sr), int(target_sr))
        out = signal.resample_poly(mono, int(target_sr) // g, int(orig_sr) // g)
        return np.asarray(out, dtype=np.float32).reshape(-1), "scipy"
    except Exception as exc:
        _audio_diag(f"scipy resample failed: {type(exc).__name__}: {exc}")
    out = librosa.resample(mono, orig_sr=int(orig_sr), target_sr=int(target_sr))
    return np.asarray(out, dtype=np.float32).reshape(-1), "librosa"


def _ffmpeg_bin() -> str:
    from shared.lib.ffmpeg_paths import resolve_ffmpeg_path

    return resolve_ffmpeg_path()


def _ffprobe_bin() -> str:
    from shared.lib.ffmpeg_paths import resolve_ffprobe_path

    return resolve_ffprobe_path()


def _load_via_ffmpeg(path_text: str, *, target_sr: int, timeout_sec: float = FFMPEG_DECODE_TIMEOUT_SEC) -> np.ndarray:
    """Decode any ffmpeg-readable audio (Opus/AAC in MP4, MP3, WAV) to mono float32."""
    ffmpeg = _ffmpeg_bin()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-i",
        path_text,
        "-ac",
        "1",
        "-ar",
        str(int(target_sr)),
        "-f",
        "f32le",
        "pipe:1",
    ]
    try:
        proc = run_hidden(
            cmd,
            capture_output=True,
            timeout=float(timeout_sec),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Audio decode timed out after {int(timeout_sec)}s (ffmpeg). The file may be unreadable."
        ) from exc
    if proc.returncode != 0 or not proc.stdout:
        detail = (proc.stderr or b"").decode("utf-8", errors="replace").strip()[:400]
        raise RuntimeError(detail or "ffmpeg could not decode this audio file.")
    y = np.frombuffer(proc.stdout, dtype=np.float32)
    if y.size < int(target_sr) * 0.2:
        raise RuntimeError("ffmpeg produced too little audio to export.")
    return y


def _load_via_librosa(path_text: str, *, target_sr: int, timeout_sec: float = LIBROSA_LOAD_TIMEOUT_SEC):
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(librosa.load, path_text, sr=int(target_sr), mono=True)
        try:
            return future.result(timeout=float(timeout_sec))
        except FuturesTimeoutError as exc:
            raise RuntimeError(
                f"Audio decode timed out after {int(timeout_sec)}s (librosa). Skipping this track."
            ) from exc


def _load_mono_waveform(path: str, *, target_sr: int, on_progress: ProgressCallback | None = None) -> tuple[np.ndarray, int, str]:
    """Decode mono PCM for analysis. Prefer soundfile (reliable in frozen installs)."""

    def _progress(message: str) -> None:
        # Never let status UI/encoding failures abort a successful decode.
        try:
            if on_progress is not None:
                on_progress(message)
        except Exception as exc:
            _audio_diag(f"progress emit failed: {type(exc).__name__}: {exc}")
        _audio_diag(message)

    target = int(max(8000, int(target_sr)))
    path_text = str(path or "").strip()
    kind = sniff_audio_container(path_text)
    _audio_diag(
        f"load_mono begin path={path_text!r} target_sr={target} "
        f"exists={Path(path_text).is_file()} container={kind}"
    )
    _audio_diag(_probe_decode_backends())

    if kind == "too_small":
        raise RuntimeError("Audio file is too small to be a real track.")

    # ISO-BMFF / WebM / raw AAC: skip mpg123/librosa — they hang or mis-read.
    if kind in _FFMPEG_FIRST_CONTAINERS:
        _progress("Loading audio (ffmpeg)...")
        t0 = time.perf_counter()
        y = _load_via_ffmpeg(path_text, target_sr=target)
        _audio_diag(
            f"ffmpeg.decode ok container={kind} duration={len(y) / max(1, target):.2f}s "
            f"took_s={time.perf_counter() - t0:.2f}"
        )
        return np.asarray(y, dtype=np.float32), target, "ffmpeg"

    # 1) Prefer soundfile — avoids librosa backend discovery hangs in PyInstaller.
    try:
        import soundfile as sf

        _progress("Loading audio (soundfile)...")
        t0 = time.perf_counter()
        data, file_sr = sf.read(path_text, always_2d=True, dtype="float32")
        read_s = time.perf_counter() - t0
        file_sr_i = int(file_sr)
        if data.ndim == 1:
            y = np.asarray(data, dtype=np.float32)
        else:
            y = np.mean(data, axis=1, dtype=np.float32)
        decoded_sec = float(len(y)) / max(1, file_sr_i)
        _audio_diag(
            f"soundfile.read ok duration={decoded_sec:.2f}s "
            f"file_sr={file_sr_i} channels={getattr(data, 'shape', None)} read_s={read_s:.2f}"
        )
        # libsndfile/minimp3 can under-decode an MP3 (VBR / 48k / odd headers)
        # without raising. A short decode here becomes a short MP4 that the export
        # gate later rejects, so refuse it and fall through to the ffmpeg decoder.
        probe_sec = _ffprobe_duration_sec(path_text)
        if probe_sec > 1.0 and decoded_sec + 0.5 < probe_sec:
            _audio_diag(
                f"soundfile decode short: {decoded_sec:.2f}s vs ffprobe {probe_sec:.2f}s "
                "-> trying ffmpeg"
            )
            raise RuntimeError(
                f"soundfile decoded {decoded_sec:.2f}s but the file is {probe_sec:.2f}s"
            )
        if file_sr_i != target:
            _progress(f"Resampling audio {file_sr_i}->{target}...")
            t1 = time.perf_counter()
            y, resample_backend = _resample_mono(y, orig_sr=file_sr_i, target_sr=target)
            _audio_diag(
                f"resample ok backend={resample_backend} samples={len(y)} "
                f"took_s={time.perf_counter() - t1:.2f}"
            )
        return y, target, "soundfile"
    except Exception as exc:
        _audio_diag(f"soundfile path failed: {type(exc).__name__}: {exc}")
        _audio_diag(traceback.format_exc())

    # 2) ffmpeg — handles MP3 that soundfile rejected, plus any leftover containers.
    try:
        _progress("Loading audio (ffmpeg)...")
        t1 = time.perf_counter()
        y = _load_via_ffmpeg(path_text, target_sr=target)
        _audio_diag(
            f"ffmpeg.decode ok duration={len(y) / max(1, target):.2f}s "
            f"took_s={time.perf_counter() - t1:.2f}"
        )
        return np.asarray(y, dtype=np.float32), target, "ffmpeg"
    except Exception as exc:
        _audio_diag(f"ffmpeg path failed: {type(exc).__name__}: {exc}")

    # 3) Last resort: librosa, but never block the export queue forever.
    _progress("Loading audio (librosa)...")
    t2 = time.perf_counter()
    try:
        y, sr = _load_via_librosa(path_text, target_sr=target)
    except Exception as exc:
        _audio_diag(f"librosa.load FAILED after {time.perf_counter() - t2:.2f}s: {type(exc).__name__}: {exc}")
        _audio_diag(traceback.format_exc())
        raise
    _audio_diag(
        f"librosa.load ok sr={sr} samples={0 if y is None else len(y)} "
        f"took_s={time.perf_counter() - t2:.2f}"
    )
    if y is None or sr is None:
        raise RuntimeError("Could not load audio")
    return np.asarray(y, dtype=np.float32), int(sr), "librosa"


def _ffprobe_duration_sec(path_text: str) -> float:
    probe = _ffprobe_bin()
    cmd = [
        probe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path_text,
    ]
    try:
        proc = run_hidden(cmd, capture_output=True, timeout=20.0, check=False, text=True)
    except (OSError, subprocess.TimeoutExpired):
        return 0.0
    if proc.returncode != 0:
        return 0.0
    try:
        return max(0.0, float((proc.stdout or "").strip()))
    except ValueError:
        return 0.0


def probe_audio_duration_sec(path: str) -> float:
    """Fast duration probe without building the full STFT analyzer.

    Used so first-play transport (seek bar / total time) works before FFT analysis
    finishes. Prefer soundfile metadata; fall back to ffmpeg/ffprobe, never librosa
    on ISO-BMFF (Opus-in-MP4) files that hang audioread.
    """
    text = str(path or "").strip()
    if not text or not Path(text).is_file():
        return 0.0
    kind = sniff_audio_container(text)
    if kind == "too_small":
        return 0.0
    if kind in _FFMPEG_FIRST_CONTAINERS:
        return _ffprobe_duration_sec(text)
    try:
        import soundfile as sf

        info = sf.info(text)
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if duration > 0:
            return duration
    except Exception:
        pass
    probed = _ffprobe_duration_sec(text)
    if probed > 0:
        return probed
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


def _beat_frames_from_onset_peaks(
    onset_env: np.ndarray,
    *,
    sr: int,
    hop_length: int,
) -> set[int]:
    """Beat frames from onset peaks.

    Frozen builds must not call ``librosa.util.peak_pick`` — it can livelock when
    another Camxora export worker already holds an OpenGL/NVENC context (UI shows
    stuck on Detecting beats… while the first track keeps rendering).
    """
    env = np.asarray(onset_env, dtype=np.float32).reshape(-1)
    if env.size == 0:
        return set()
    # ~240ms spacing ≈ 250 BPM upper bound — good enough for visualizer pulses.
    wait = max(1, int(round(0.24 * float(max(1, sr)) / float(max(1, hop_length)))))
    if not _is_frozen():
        try:
            peaks = librosa.util.peak_pick(
                env,
                pre_max=max(1, wait // 4),
                post_max=max(1, wait // 4),
                pre_avg=max(1, wait // 2),
                post_avg=max(1, wait // 2),
                delta=0.05,
                wait=wait,
            )
            return {int(x) for x in np.asarray(peaks).reshape(-1).tolist()}
        except Exception as exc:
            _audio_diag(f"peak_pick failed: {type(exc).__name__}: {exc}")
    try:
        from scipy.signal import find_peaks

        peaks, _props = find_peaks(env, distance=wait, height=0.15)
        return {int(x) for x in np.asarray(peaks).reshape(-1).tolist()}
    except Exception as exc:
        _audio_diag(f"find_peaks failed: {type(exc).__name__}: {exc}")
    # Pure NumPy fallback — never block the export pipeline on beat detection.
    peaks_list: list[int] = []
    last = -wait
    threshold = 0.15
    for i in range(1, int(env.size) - 1):
        v = float(env[i])
        if v < threshold:
            continue
        if v >= float(env[i - 1]) and v >= float(env[i + 1]) and (i - last) >= wait:
            peaks_list.append(i)
            last = i
    return set(peaks_list)


@contextmanager
def _frozen_analysis_lock() -> Iterator[None]:
    """Serialize AudioAnalyzer across frozen worker processes.

    Encoding may still run in parallel after analysis; only the heavy analysis
    critical section is exclusive (avoids OpenBLAS/librosa cross-talk).
    """
    if not _is_frozen() or sys.platform != "win32":
        yield
        return
    handle = None
    kernel32 = None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.CreateMutexW(None, False, "Local\\CamxoraAudioAnalysisLock")
        if handle:
            # Wait up to 10 minutes for another worker to finish analysis.
            kernel32.WaitForSingleObject(handle, 600_000)
        yield
    finally:
        if handle and kernel32 is not None:
            try:
                kernel32.ReleaseMutex(handle)
            except Exception:
                pass
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass


def _spectrum_mag_numpy(y: np.ndarray, *, n_fft: int, hop_length: int) -> np.ndarray:
    """Hann-windowed STFT magnitude using NumPy only (no SciPy)."""
    mono = np.asarray(y, dtype=np.float32).reshape(-1)
    n_fft_i = int(max(16, n_fft))
    hop_i = int(max(1, hop_length))
    if mono.size < n_fft_i:
        mono = np.pad(mono, (0, int(n_fft_i - mono.size)))
    window = np.hanning(n_fft_i).astype(np.float32)
    frames = 1 + max(0, (int(mono.size) - n_fft_i) // hop_i)
    if frames <= 0:
        return np.zeros((n_fft_i // 2 + 1, 0), dtype=np.float32)
    # Shape (frames, n_fft) then rfft → (n_fft//2+1, frames)
    idx = (np.arange(n_fft_i, dtype=np.int64)[None, :] + (np.arange(frames, dtype=np.int64) * hop_i)[:, None])
    framed = mono[idx] * window[None, :]
    spec = np.fft.rfft(framed, n=n_fft_i, axis=1)
    return np.abs(spec).astype(np.float32).T


def _spectrum_mag_frozen(y: np.ndarray, *, n_fft: int, hop_length: int) -> np.ndarray:
    """STFT magnitude without librosa/OpenBLAS — safe under parallel frozen workers."""
    try:
        from scipy import signal

        mono = np.asarray(y, dtype=np.float32).reshape(-1)
        n_fft_i = int(max(16, n_fft))
        hop_i = int(max(1, hop_length))
        noverlap = int(max(0, n_fft_i - hop_i))
        _freqs, _times, zxx = signal.stft(
            mono,
            fs=1.0,
            window="hann",
            nperseg=n_fft_i,
            noverlap=noverlap,
            nfft=n_fft_i,
            boundary=None,
            padded=False,
        )
        return np.abs(zxx).astype(np.float32)
    except Exception as exc:
        _audio_diag(f"scipy STFT unavailable ({type(exc).__name__}: {exc}); using NumPy STFT")
        return _spectrum_mag_numpy(y, n_fft=n_fft, hop_length=hop_length)


def _onset_from_mag(mag: np.ndarray) -> np.ndarray:
    """Spectral-flux onset from an existing magnitude spectrogram (no second STFT)."""
    if mag.size == 0:
        return np.zeros((0,), dtype=np.float32)
    # Positive spectral flux across frequency bins.
    diff = np.diff(mag, axis=1, prepend=mag[:, :1])
    flux = np.maximum(0.0, diff).sum(axis=0).astype(np.float32)
    peak = float(np.max(flux)) if flux.size else 0.0
    if peak > 1e-9:
        flux = flux / peak
    return flux


def _fft_freqs(sr: int, n_fft: int) -> np.ndarray:
    return (np.arange(0, int(n_fft) // 2 + 1, dtype=np.float32) * (float(sr) / float(n_fft)))


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
            try:
                if on_progress is not None:
                    on_progress(message)
            except Exception as exc:
                _audio_diag(f"progress emit failed: {type(exc).__name__}: {exc}")
            _audio_diag(message)

        started = time.perf_counter()
        _audio_diag(f"AudioAnalyzer start path={mp3_path!r} fps={fps} points={point_count}")
        with _frozen_analysis_lock(), _blas_thread_limit():
            y, sr, backend = _load_mono_waveform(
                mp3_path,
                target_sr=int(max(8000, int(analysis_sr))),
                on_progress=on_progress,
            )
            _progress(f"Audio decode ready ({backend}, {len(y) / max(1, sr):.1f}s)...")
            self._sr = int(sr)
            self._fps = int(fps)
            self._point_count = int(point_count)
            self._n_fft = int(n_fft)
            self._hop_length = max(1, int(round(self._sr / max(1, self._fps))))
            self._analyze_waveform(y, on_progress=_progress)
        _audio_diag(f"AudioAnalyzer done backend={backend} total_s={time.perf_counter() - started:.2f}")

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
            try:
                if on_progress is not None:
                    on_progress(message)
            except Exception as exc:
                _audio_diag(f"progress emit failed: {type(exc).__name__}: {exc}")
            _audio_diag(message)

        t0 = time.perf_counter()
        _progress("Computing spectrum...")
        if _is_frozen():
            mag = _spectrum_mag_frozen(y, n_fft=self._n_fft, hop_length=self._hop_length)
            spectrum_backend = "scipy.stft"
        else:
            stft = librosa.stft(
                y, n_fft=self._n_fft, hop_length=self._hop_length, window="hann", center=True
            )
            mag = np.abs(stft).astype(np.float32)
            spectrum_backend = "librosa.stft"
        mag_max = float(np.max(mag)) if mag.size else 1.0
        self._mag = mag / max(1e-9, mag_max)
        _audio_diag(
            f"spectrum ok shape={self._mag.shape} backend={spectrum_backend} "
            f"took_s={time.perf_counter() - t0:.2f}"
        )

        freqs = _fft_freqs(self._sr, self._n_fft)
        self._freqs = freqs
        self._bass_idx = np.where((freqs >= 20.0) & (freqs < 200.0))[0]
        self._mid_idx = np.where((freqs >= 200.0) & (freqs < 2000.0))[0]
        self._treble_idx = np.where((freqs >= 2000.0) & (freqs < 8000.0))[0]

        duration = float(len(y) / max(1, self._sr))
        frames = int(np.ceil(duration * self._fps))
        self._info = AudioInfo(sample_rate=self._sr, duration_sec=duration, frames=frames)

        self._freq_bins = self._mag.shape[0]
        self._frames_bins = self._mag.shape[1]
        self._x_in = np.linspace(0.0, 1.0, num=self._freq_bins, dtype=np.float32)
        self._x_out = np.linspace(0.0, 1.0, num=self._point_count, dtype=np.float32)
        self._fft_out = np.zeros(self._point_count, dtype=np.float32)
        self._feat_cache_idx = -1
        self._feat_cache: dict = {}

        t1 = time.perf_counter()
        _progress("Detecting onset...")
        if _is_frozen():
            onset_env = _onset_from_mag(self._mag)
            onset_backend = "spectral_flux"
        else:
            onset_env = librosa.onset.onset_strength(y=y, sr=self._sr, hop_length=self._hop_length)
            onset_env = onset_env.astype(np.float32)
            if onset_env.size:
                onset_env = onset_env / max(1e-9, float(np.max(onset_env)))
            onset_backend = "librosa.onset"
        self._onset_env = onset_env
        _audio_diag(
            f"onset ok frames={onset_env.size} backend={onset_backend} "
            f"took_s={time.perf_counter() - t1:.2f}"
        )

        t2 = time.perf_counter()
        _progress("Detecting beats...")
        # librosa.beat.beat_track can native-crash (0xC0000005) in frozen PyInstaller
        # builds; peak-pick on the onset envelope is enough for visualizer beat pulses.
        beat_set: set[int] = set()
        beat_backend = "none"
        try:
            if _is_frozen():
                beat_set = _beat_frames_from_onset_peaks(
                    onset_env, sr=self._sr, hop_length=self._hop_length
                )
                beat_backend = "onset_peaks"
            else:
                _tempo, beat_frames = librosa.beat.beat_track(
                    onset_envelope=onset_env,
                    sr=self._sr,
                    hop_length=self._hop_length,
                    units="frames",
                )
                beat_set = {int(x) for x in np.asarray(beat_frames).reshape(-1).tolist()}
                beat_backend = f"librosa_tempo={_tempo!r}"
            _audio_diag(
                f"beats ok count={len(beat_set)} backend={beat_backend} "
                f"took_s={time.perf_counter() - t2:.2f}"
            )
        except Exception as exc:
            _audio_diag(f"beats failed: {type(exc).__name__}: {exc}")
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
