"""Persist librosa STFT analysis so preview and export can reuse it.

The cache is a flat directory of ``<sha1>.npz`` pairs (array data) plus a
``<sha1>.meta.json`` sidecar used to validate the entry. Nothing used to
delete these files, so a busy machine accumulated tens of gigabytes. Writes
now go through :func:`prune_audio_analysis_cache`, which enforces a disk
budget, an age limit, and removes entries from older cache versions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from shared.lib.app_paths import get_user_data_dir

if TYPE_CHECKING:
    from visualizer.audio import AudioAnalyzer

log = logging.getLogger(__name__)

CACHE_VERSION = 4
CACHE_DIR_NAME = "audio-analysis"

# Entries are ~10-25 MB after the float16 magnitude change, so 2 GiB holds
# roughly 100 recent tracks. Override with CAMXORA_AUDIO_CACHE_MAX_MB.
DEFAULT_CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024
MIN_CACHE_MAX_BYTES = 256 * 1024 * 1024
CACHE_RETENTION_DAYS = 30
# Pruning scans the directory, so throttle the write-time sweep.
PRUNE_INTERVAL_SEC = 10 * 60
# A partial write older than this is a crash leftover, not an in-flight write.
PARTIAL_MAX_AGE_SEC = 60 * 60

_NPZ_SUFFIX = ".npz"
_META_SUFFIX = ".meta.json"
_PARTIAL_SUFFIX = ".part"

_prune_lock = threading.Lock()
_last_prune_at = 0.0


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


def get_audio_analysis_cache_max_bytes() -> int:
    raw = str(os.environ.get("CAMXORA_AUDIO_CACHE_MAX_MB") or "").strip()
    if raw:
        try:
            megabytes = int(float(raw))
        except ValueError:
            megabytes = 0
        if megabytes > 0:
            return max(MIN_CACHE_MAX_BYTES, megabytes * 1024 * 1024)
    return DEFAULT_CACHE_MAX_BYTES


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
    return base.with_suffix(_NPZ_SUFFIX), base.with_suffix(_META_SUFFIX)


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
        with np.load(npz_path, allow_pickle=False) as data:
            cached_duration = float(data["duration_sec"])
            sample_rate = int(data["sample_rate"])
            hop_length = int(data["hop_length"])
            mag = np.asarray(data["mag"], dtype=np.float32)
            onset_env = np.asarray(data["onset_env"], dtype=np.float32)
            beat_frames = np.asarray(data["beat_frames"], dtype=np.int32)
        # A cache written before a decoder fix can hold a too-short duration
        # (libsndfile/minimp3 under-decodes some 48 kHz VBR MP3s). Reject it so
        # the export re-analyzes with the current decoder instead of rendering a
        # short MP4 from the stale length.
        try:
            from visualizer.audio import _ffprobe_duration_sec

            probe_duration = float(_ffprobe_duration_sec(key.source_path) or 0.0)
        except Exception:
            probe_duration = 0.0
        if probe_duration > 1.0 and cached_duration + 0.5 < probe_duration:
            log.warning(
                "analysis cache duration short (%.1fs vs %.1fs); re-analyzing %s",
                cached_duration,
                probe_duration,
                Path(key.source_path).name,
            )
            _safe_unlink(npz_path)
            _safe_unlink(meta_path)
            return None
        from visualizer.audio import AudioAnalyzer

        analyzer = AudioAnalyzer.from_cached_arrays(
            fps=key.fps,
            point_count=key.point_count,
            n_fft=key.n_fft,
            sample_rate=sample_rate,
            hop_length=hop_length,
            duration_sec=cached_duration,
            mag=mag,
            onset_env=onset_env,
            beat_frames=beat_frames,
        )
        # Keep LRU order meaningful on Windows, where last-access updates are
        # often delayed or disabled.
        _touch(npz_path)
        _touch(meta_path)
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
    npz_part = npz_path.with_name(npz_path.name + _PARTIAL_SUFFIX)
    meta_part = meta_path.with_name(meta_path.name + _PARTIAL_SUFFIX)
    try:
        # float16 halves the largest array and is plenty for a normalized
        # 0..1 magnitude spectrum. Derived arrays (freqs, band indices) are
        # rebuilt on load instead of being stored per entry.
        with npz_part.open("wb") as handle:
            np.savez_compressed(
                handle,
                sample_rate=np.int32(analyzer._sr),
                hop_length=np.int32(analyzer._hop_length),
                duration_sec=np.float32(analyzer.info.duration_sec),
                mag=np.asarray(analyzer._mag, dtype=np.float16),
                onset_env=np.asarray(analyzer._onset_env, dtype=np.float32),
                beat_frames=np.asarray(sorted(analyzer._beat_set), dtype=np.int32),
            )
        meta_part.write_text(
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
        os.replace(npz_part, npz_path)
        os.replace(meta_part, meta_path)
        log.info("analysis cache saved: %s", Path(key.source_path).name)
    except Exception as exc:
        log.warning("analysis cache write failed: %s", exc)
        _safe_unlink(npz_part)
        _safe_unlink(meta_part)
        _safe_unlink(npz_path)
        _safe_unlink(meta_path)
        return
    _prune_after_write()


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
    from visualizer.audio import AudioAnalyzer

    analyzer = AudioAnalyzer(mp3_path, fps=fps, point_count=point_count, n_fft=n_fft)
    if use_cache:
        set_audio_analysis_cache(analyzer, mp3_path)
    return analyzer, False


def audio_analysis_cache_stats() -> dict[str, int]:
    """Return ``entries``, ``totalBytes``, ``maxBytes`` for the cache directory."""
    directory = get_audio_analysis_cache_dir()
    entries = 0
    total_bytes = 0
    try:
        for npz_path in directory.glob(f"*{_NPZ_SUFFIX}"):
            meta_path = npz_path.with_name(npz_path.name[: -len(_NPZ_SUFFIX)] + _META_SUFFIX)
            if not meta_path.is_file():
                continue
            entries += 1
            try:
                total_bytes += npz_path.stat().st_size + meta_path.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return {
        "entries": entries,
        "totalBytes": total_bytes,
        "maxBytes": get_audio_analysis_cache_max_bytes(),
    }


def prune_audio_analysis_cache(
    *,
    max_bytes: int | None = None,
    max_age_days: float | None = None,
) -> dict[str, int]:
    """Delete stale cache entries and keep the directory under its budget.

    Removes broken pairs (``.npz`` without meta and vice versa), entries from
    older ``CACHE_VERSION`` builds, entries older than ``max_age_days``, and
    finally the least recently used entries until ``max_bytes`` is met.
    """
    global _last_prune_at
    directory = get_audio_analysis_cache_dir()
    limit = int(max_bytes if max_bytes is not None else get_audio_analysis_cache_max_bytes())
    age_days = float(CACHE_RETENTION_DAYS if max_age_days is None else max_age_days)
    now = time.time()

    with _prune_lock:
        _last_prune_at = now
        entries: list[_CacheEntry] = []
        deleted_entries = 0
        deleted_bytes = 0

        try:
            children = list(directory.iterdir())
        except OSError:
            return {"entries": 0, "totalBytes": 0, "deletedEntries": 0, "deletedBytes": 0}

        files: dict[str, dict[str, Path]] = {}
        for path in children:
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            if path.name.endswith(_PARTIAL_SUFFIX):
                _delete_partial(path, now)
                continue
            if path.name.endswith(_META_SUFFIX):
                files.setdefault(path.name[: -len(_META_SUFFIX)], {})["meta"] = path
            elif path.name.endswith(_NPZ_SUFFIX):
                files.setdefault(path.name[: -len(_NPZ_SUFFIX)], {})["npz"] = path

        for stem, pair in files.items():
            npz_path = pair.get("npz")
            meta_path = pair.get("meta")
            if npz_path is None or meta_path is None:
                for orphan in pair.values():
                    freed = _delete_entry_file(orphan)
                    if freed:
                        deleted_entries += 1
                        deleted_bytes += freed
                continue
            meta = _read_meta(meta_path)
            if meta is None or int(meta.get("version", 0)) != CACHE_VERSION:
                freed = _delete_entry_file(npz_path) + _delete_entry_file(meta_path)
                deleted_entries += 1
                deleted_bytes += freed
                continue
            try:
                npz_stat = npz_path.stat()
                meta_stat = meta_path.stat()
            except OSError:
                continue
            entries.append(
                _CacheEntry(
                    npz=npz_path,
                    meta=meta_path,
                    bytes=int(npz_stat.st_size) + int(meta_stat.st_size),
                    last_used=max(npz_stat.st_atime, npz_stat.st_mtime, meta_stat.st_mtime),
                )
            )

        cutoff = now - max(0.0, age_days) * 86400
        kept: list[_CacheEntry] = []
        for entry in entries:
            if entry.last_used < cutoff:
                freed = _delete_entry_file(entry.npz) + _delete_entry_file(entry.meta)
                deleted_entries += 1
                deleted_bytes += freed
            else:
                kept.append(entry)

        total_bytes = sum(entry.bytes for entry in kept)
        kept.sort(key=lambda entry: entry.last_used)
        while kept and total_bytes > limit:
            entry = kept.pop(0)
            freed = _delete_entry_file(entry.npz) + _delete_entry_file(entry.meta)
            deleted_entries += 1
            deleted_bytes += freed
            total_bytes -= entry.bytes

    if deleted_entries:
        log.info(
            "analysis cache pruned: %d entries, %.1f MB freed, %.1f MB remaining",
            deleted_entries,
            deleted_bytes / (1024 * 1024),
            total_bytes / (1024 * 1024),
        )
    return {
        "entries": len(kept),
        "totalBytes": total_bytes,
        "deletedEntries": deleted_entries,
        "deletedBytes": deleted_bytes,
    }


def clear_audio_analysis_cache() -> dict[str, int]:
    """Delete every cache file. Analysis re-runs on the next preview/export."""
    directory = get_audio_analysis_cache_dir()
    deleted_entries = 0
    deleted_bytes = 0
    try:
        children = list(directory.iterdir())
    except OSError:
        return {"deletedEntries": 0, "deletedBytes": 0}
    for path in children:
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        freed = _delete_entry_file(path)
        if freed:
            if path.name.endswith(_NPZ_SUFFIX):
                deleted_entries += 1
            deleted_bytes += freed
    if deleted_entries:
        log.info(
            "analysis cache cleared: %d entries, %.1f MB freed",
            deleted_entries,
            deleted_bytes / (1024 * 1024),
        )
    return {"deletedEntries": deleted_entries, "deletedBytes": deleted_bytes}


@dataclass(frozen=True)
class _CacheEntry:
    npz: Path
    meta: Path
    bytes: int
    last_used: float


def _read_meta(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _prune_after_write() -> None:
    now = time.time()
    if now - _last_prune_at < PRUNE_INTERVAL_SEC:
        return
    try:
        prune_audio_analysis_cache()
    except Exception as exc:  # pragma: no cover - pruning must never break writes
        log.debug("analysis cache prune failed: %s", exc)


def _delete_partial(path: Path, now: float) -> None:
    """Only remove pre-existing partial writes, never a concurrent one."""
    try:
        if now - path.stat().st_mtime > PARTIAL_MAX_AGE_SEC:
            _safe_unlink(path)
    except OSError:
        pass


def _delete_entry_file(path: Path) -> int:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return 0
    return size


def _touch(path: Path) -> None:
    try:
        os.utime(path, None)
    except OSError:
        pass


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
