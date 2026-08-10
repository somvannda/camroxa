"""Native NVENC encode writer — pipelined RGBA→NV12→Annex-B H.264 (REQ-3.5).

When ``CAMXORA_NATIVE_ENCODE=1`` and the DLL loads, export can bypass the ffmpeg
rawvideo pipe for video. Packing runs on a writer thread (like PipelinedEncodeWriter);
``CAMXORA_NATIVE_ENCODE_EXPORT=1`` also enables the path. Audio is remuxed afterward
with ``ffmpeg -c:v copy``.
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from visualizer_video.encode_pipeline import resolve_encode_queue_size

logger = logging.getLogger(__name__)

_SENTINEL = object()

# NVENC on some GPUs rejects very small surfaces (smoke: 144 failed, 256 ok).
_MIN_NATIVE_DIM = 256


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _env_truthy(name: str) -> bool:
    raw = str(os.environ.get(name, "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def native_encode_preferred() -> bool:
    """Return True when export should try the native NVENC bridge.

    Primary flag: ``CAMXORA_NATIVE_ENCODE=1``. Optional override
    ``CAMXORA_NATIVE_ENCODE_EXPORT=1`` also enables (same effect).
    """
    return _env_truthy("CAMXORA_NATIVE_ENCODE") or _env_truthy(
        "CAMXORA_NATIVE_ENCODE_EXPORT"
    )


def native_encode_dims_ok(width: int, height: int) -> bool:
    return int(width) >= _MIN_NATIVE_DIM and int(height) >= _MIN_NATIVE_DIM


def try_open_native_encode_writer(
    *,
    width: int,
    height: int,
    fps: int,
    h264_path: str,
    bitrate_kbps: int = 0,
) -> NativeEncodeWriter | None:
    """Return a live writer, or None to keep the ffmpeg pipe path."""
    if not native_encode_preferred():
        return None
    if not native_encode_dims_ok(width, height):
        logger.info(
            "native encode skipped: %sx%s below %s min",
            width,
            height,
            _MIN_NATIVE_DIM,
        )
        return None
    try:
        from features.video.services.native_encode_bridge import (
            NativeEncodeSession,
            is_available,
            probe,
        )
    except Exception as exc:
        logger.debug("native encode import failed: %s", exc)
        return None
    if not is_available():
        return None
    try:
        session = NativeEncodeSession(
            width=width,
            height=height,
            fps=fps,
            output_path=h264_path,
            bitrate_kbps=bitrate_kbps,
        )
        session.__enter__()
    except (NotImplementedError, RuntimeError, OSError) as exc:
        logger.info("native encode create failed, pipe fallback: %s", exc)
        return None
    gpu = ""
    try:
        gpu = probe()
    except Exception:
        pass
    logger.info("native NVENC encode active probe=%s out=%s", gpu or "?", h264_path)
    return NativeEncodeWriter(session, h264_path=h264_path, width=width, height=height)


class NativeEncodeWriter:
    """Bounded queue + writer thread: pack RGBA→NV12, then native NVENC submit."""

    def __init__(
        self,
        session: Any,
        *,
        h264_path: str,
        width: int,
        height: int,
        queue_size: int | None = None,
    ) -> None:
        self._session = session
        self._h264_path = h264_path
        self._width = int(width)
        self._height = int(height)
        self._stride = self._width * 4
        self._use_nv12 = bool(getattr(session, "supports_nv12", lambda: False)())

        size = resolve_encode_queue_size(queue_size)
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=size)
        self._stop = threading.Event()
        self._cancelled = False
        self._finished = False
        self._error: Exception | None = None

        self._submit_block_times_ms: list[float] = []
        self._pack_times_ms: list[float] = []
        self._submit_encode_times_ms: list[float] = []
        self._frames_submitted = 0
        self._frames_encoded = 0

        self._thread = threading.Thread(
            target=self._writer_loop,
            name="camxora-native-encode",
            daemon=True,
        )
        self._thread.start()

    @property
    def h264_path(self) -> str:
        return self._h264_path

    def submit(self, raw_rgba: Any) -> None:
        """Enqueue one RGBA frame (copied so the buffer pool can reuse)."""
        self._raise_if_error()
        if self._finished or self._cancelled:
            return
        # Copy so AsyncFramebufferReader / CPU pool can reclaim the buffer.
        payload = bytes(raw_rgba)
        t0 = time.perf_counter()
        while not self._finished and not self._cancelled:
            if self._stop.is_set():
                self._raise_if_error()
                return
            try:
                from features.video.lib.export_cancel import export_cancel_requested

                if export_cancel_requested():
                    self._cancelled = True
                    self._finished = True
                    self._stop.set()
                    return
            except Exception:
                pass
            try:
                self._queue.put(payload, timeout=0.05)
                break
            except queue.Full:
                continue
        self._submit_block_times_ms.append((time.perf_counter() - t0) * 1000.0)
        self._frames_submitted += 1

    def cancel(self, *, terminate_process: bool = True) -> None:
        """Stop the writer and destroy the encode session."""
        del terminate_process  # no ffmpeg process; kept for pipe-writer API parity
        if self._finished and not self._thread.is_alive():
            return
        self._cancelled = True
        self._finished = True
        self._stop.set()
        self._drain_queue()
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        self._thread.join(timeout=2.0)
        try:
            self._session.__exit__(None, None, None)
        except Exception:
            pass

    def finish(self) -> None:
        """Drain queue, finish NVENC, destroy session."""
        if self._finished and not self._thread.is_alive():
            self._raise_if_error()
            return
        if self._cancelled:
            self.cancel()
            return
        self._finished = True
        try:
            self._queue.put(_SENTINEL, timeout=1.0)
        except queue.Full:
            self._drain_queue()
            self._queue.put(_SENTINEL, timeout=1.0)
        self._thread.join(timeout=60.0)
        try:
            self._raise_if_error()
            self._session.finish()
        finally:
            try:
                self._session.__exit__(None, None, None)
            except Exception:
                pass

    def stats(self) -> dict[str, Any]:
        return {
            "framesSubmitted": self._frames_submitted,
            "framesEncoded": self._frames_encoded,
            "queueSize": self._queue.maxsize,
            "backend": "native_nvenc",
            "submitNv12": self._use_nv12,
            "submitBlockP95Ms": _percentile(self._submit_block_times_ms, 95.0),
            "packAvgMs": (
                (sum(self._pack_times_ms) / len(self._pack_times_ms))
                if self._pack_times_ms
                else None
            ),
            "packP95Ms": _percentile(self._pack_times_ms, 95.0),
            "submitEncodeP95Ms": _percentile(self._submit_encode_times_ms, 95.0),
        }

    def _drain_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _raise_if_error(self) -> None:
        if self._error is not None:
            raise self._error

    def _writer_loop(self) -> None:
        try:
            from visualizer_video.readback import PipeFramePacker

            packer = (
                PipeFramePacker(self._width, self._height, "nv12")
                if self._use_nv12
                else None
            )
            while True:
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                if item is _SENTINEL:
                    break
                if self._cancelled:
                    continue
                if packer is not None:
                    t_pack = time.perf_counter()
                    nv12 = packer(item)
                    self._pack_times_ms.append(
                        (time.perf_counter() - t_pack) * 1000.0
                    )
                    t_enc = time.perf_counter()
                    self._session.submit_nv12(nv12, self._width)
                    self._submit_encode_times_ms.append(
                        (time.perf_counter() - t_enc) * 1000.0
                    )
                else:
                    t_enc = time.perf_counter()
                    self._session.submit_rgba(item, self._stride)
                    self._submit_encode_times_ms.append(
                        (time.perf_counter() - t_enc) * 1000.0
                    )
                self._frames_encoded += 1
        except Exception as exc:
            self._error = exc
            self._stop.set()


def remux_native_h264_with_audio(
    *,
    ffmpeg_path: str,
    h264_path: str,
    mp3_path: str,
    out_path: str,
) -> None:
    """Mux Annex-B H.264 + audio into MP4 (video stream copy)."""
    cmd = [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-fflags",
        "+genpts",
        "-i",
        str(h264_path),
        "-i",
        str(mp3_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(out_path),
    ]
    from shared.lib.subprocess_utils import popen_hidden

    err_path = Path(out_path).parent / f"ffmpeg_native_remux_{os.getpid()}.log"
    with open(err_path, "w+", encoding="utf-8") as err_file:
        proc = popen_hidden(cmd, stdin=subprocess.DEVNULL, stderr=err_file)
        code = int(proc.wait())
        if code != 0:
            err_file.seek(0)
            detail = (err_file.read() or "").strip()
            raise RuntimeError(detail or f"native remux failed (exit {code})")
    try:
        err_path.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        Path(h264_path).unlink(missing_ok=True)
    except Exception:
        pass
