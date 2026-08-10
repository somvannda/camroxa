"""Persist librosa STFT analysis so preview and export can reuse it."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from shared.lib.app_paths import get_user_data_dir

if TYPE_CHECKING:
    from visualizer_video.audio import AudioAnalyzer

log = logging.getLogger(__name__)

CACHE_VERSION = 2
CACHE_DIR_NAME = "audio-analysis"


@dataclass(frozen=True)
class AudioAnalysisCacheKey:
    source_path: str
    file_size: int
    file_mtime_ns: int
    fps: int
    point_count: int
    n_fft: int

    def digest(self) -> str:
        raw = (
            f"v{CACHE_VERSION}|{self.source_path}|{self.file_size}|{self.file_mtime_ns}|"
            f"{self.fps}|{self.point_count}|{self.n_fft}"
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def get_audio_analysis_cache_dir() -> Path:
    path = get_user_data_dir() / "cache" / CACHE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_audio_analysis_cache_key(
    mp3_path: str,
    *,
    fps: int,
    point_count: int,
    n_fft: int = 2048,
) -> AudioAnalysisCacheKey | None:
    path = Path(str(mp3_path or "").strip())
    if not path.is_file():
        return None
    stat = path.stat()
    return AudioAnalysisCacheKey(
        source_path=str(path.resolve()),
        file_size=int(stat.st_size),
        file_mtime_ns=int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
        fps=int(fps),
        point_count=int(point_count),
        n_fft=int(n_fft),
    )


def _cache_paths(key: AudioAnalysisCacheKey) -> tuple[Path, Path]:
    base = get_audio_analysis_cache_dir() / key.digest()
    return base.with_suffix(".npz"), base.with_suffix(".meta.json")


def get_audio_analysis_cache(
    mp3_path: str,
    *,
    fps: int,
    point_count: int,
    n_fft: int = 2048,
) -> AudioAnalyzer | None:
    key = build_audio_analysis_cache_key(mp3_path, fps=fps, point_count=point_count, n_fft=n_fft)
    if key is None:
        return None
    npz_path, meta_path = _cache_paths(key)
    if not npz_path.is_file() or not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if int(meta.get("version", 0)) != CACHE_VERSION:
            return None
        if (
            str(meta.get("sourcePath") or "") != key.source_path
            or int(meta.get("fileSize") or -1) != key.file_size
            or int(meta.get("fileMtimeNs") or -1) != key.file_mtime_ns
            or int(meta.get("fps") or -1) != key.fps
            or int(meta.get("pointCount") or -1) != key.point_count
            or int(meta.get("nFft") or -1) != key.n_fft
        ):
            return None
        data = np.load(npz_path, allow_pickle=False)
        from visualizer_video.audio import AudioAnalyzer

        analyzer = AudioAnalyzer.from_cached_arrays(
            fps=key.fps,
            point_count=key.point_count,
            n_fft=key.n_fft,
            sample_rate=int(data["sample_rate"]),
            hop_length=int(data["hop_length"]),
            duration_sec=float(data["duration_sec"]),
            mag=data["mag"],
            freqs=data["freqs"],
            bass_idx=data["bass_idx"],
            mid_idx=data["mid_idx"],
            treble_idx=data["treble_idx"],
            onset_env=data["onset_env"],
            beat_frames=data["beat_frames"],
        )
        log.info("analysis cache hit: %s", Path(key.source_path).name)
        return analyzer
    except Exception as exc:
        log.warning("analysis cache read failed (%s): %s", npz_path.name, exc)
        _safe_unlink(npz_path)
        _safe_unlink(meta_path)
        return None


def set_audio_analysis_cache(analyzer: AudioAnalyzer, mp3_path: str) -> None:
    key = build_audio_analysis_cache_key(
        mp3_path,
        fps=int(analyzer.fps),
        point_count=int(analyzer.point_count),
        n_fft=int(getattr(analyzer, "_n_fft", 2048)),
    )
    if key is None:
        return
    npz_path, meta_path = _cache_paths(key)
    try:
        np.savez_compressed(
            npz_path,
            sample_rate=np.int32(analyzer._sr),
            hop_length=np.int32(analyzer._hop_length),
            duration_sec=np.float32(analyzer.info.duration_sec),
            mag=analyzer._mag,
            freqs=analyzer._freqs,
            bass_idx=analyzer._bass_idx,
            mid_idx=analyzer._mid_idx,
            treble_idx=analyzer._treble_idx,
            onset_env=analyzer._onset_env,
            beat_frames=np.asarray(sorted(analyzer._beat_set), dtype=np.int32),
        )
        meta_path.write_text(
            json.dumps(
                {
                    "version": CACHE_VERSION,
                    "sourcePath": key.source_path,
                    "fileSize": key.file_size,
                    "fileMtimeNs": key.file_mtime_ns,
                    "fps": key.fps,
                    "pointCount": key.point_count,
                    "nFft": key.n_fft,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        log.info("analysis cache saved: %s", Path(key.source_path).name)
    except Exception as exc:
        log.warning("analysis cache write failed: %s", exc)
        _safe_unlink(npz_path)
        _safe_unlink(meta_path)


def load_audio_analyzer(
    mp3_path: str,
    *,
    fps: int,
    point_count: int,
    n_fft: int = 2048,
    use_cache: bool = True,
) -> tuple[AudioAnalyzer, bool]:
    """Return analyzer and whether it was loaded from disk cache."""
    if use_cache:
        cached = get_audio_analysis_cache(mp3_path, fps=fps, point_count=point_count, n_fft=n_fft)
        if cached is not None:
            return cached, True
    from visualizer_video.audio import AudioAnalyzer

    analyzer = AudioAnalyzer(mp3_path, fps=fps, point_count=point_count, n_fft=n_fft)
    if use_cache:
        set_audio_analysis_cache(analyzer, mp3_path)
    return analyzer, False


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
