"""Pipelined ffmpeg stdin writer — decouple render loop from slow pipe ingest (REQ-2.4)."""

from __future__ import annotations

import os
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

_SENTINEL = object()
_DEFAULT_QUEUE_SIZE = 6
_MIN_QUEUE_SIZE = 2
_MAX_QUEUE_SIZE = 8


def pipelined_encode_enabled() -> bool:
    raw = str(os.environ.get("CAMXORA_PIPELINED_ENCODE", "1") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def resolve_encode_queue_size(requested: int | None = None) -> int:
    """Bounded encode queue depth (default 6; override via CAMXORA_ENCODE_QUEUE)."""
    if requested is not None:
        return int(max(_MIN_QUEUE_SIZE, min(_MAX_QUEUE_SIZE, int(requested))))
    raw = str(os.environ.get("CAMXORA_ENCODE_QUEUE", "") or "").strip()
    if raw.isdigit():
        return int(max(_MIN_QUEUE_SIZE, min(_MAX_QUEUE_SIZE, int(raw))))
    return _DEFAULT_QUEUE_SIZE


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


def _ffmpeg_err_text(enc: Any, err_file: Any) -> str:
    if err_file is not None:
        try:
            err_file.seek(0)
            return str(err_file.read() or "")
        except Exception:
            return ""
    return ""


class PipelinedEncodeWriter:
    """Bounded queue + writer thread between render loop and ffmpeg stdin.

    Optional ``pack_fn`` moves CPU packing (e.g. RGBA→NV12) onto the writer
    thread so the render loop only enqueues raw readback bytes.
    """

    def __init__(
        self,
        enc: Any,
        *,
        queue_size: int | None = None,
        err_file: Any = None,
        pack_fn: Callable[[Any], Any] | None = None,
    ) -> None:
        size = resolve_encode_queue_size(queue_size)
        self._enc = enc
        self._err_file = err_file
        self._pack_fn = pack_fn
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=size)
        self._stop = threading.Event()
        self._cancelled = False
        self._error: Exception | None = None
        self._closed = False

        self._submit_block_times_ms: list[float] = []
        self._pack_times_ms: list[float] = []
        self._stdin_block_times_ms: list[float] = []
        self._frames_submitted = 0
        self._frames_written = 0

        self._thread = threading.Thread(
            target=self._writer_loop,
            name="camxora-encode-writer",
            daemon=True,
        )
        self._thread.start()

    def submit(self, payload: Any) -> None:
        """Enqueue one frame payload; blocks when queue is full (back-pressure)."""
        self._raise_if_error()
        if self._closed:
            return
        t0 = time.perf_counter()
        while not self._closed:
            if self._stop.is_set():
                self._raise_if_error()
                return
            # Cooperative cancel while blocked on a full encode queue (daemon
            # exports previously had no cancel_check between frames).
            try:
                from features.video.lib.export_cancel import export_cancel_requested

                if export_cancel_requested():
                    self._cancelled = True
                    self._closed = True
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

    def finish(self) -> None:
        """Drain queued frames, close stdin, and wait for the writer thread."""
        if self._closed:
            self._raise_if_error()
            return
        self._closed = True
        try:
            self._queue.put(_SENTINEL, timeout=1.0)
        except queue.Full:
            self._drain_queue()
            self._queue.put(_SENTINEL, timeout=1.0)
        self._thread.join(timeout=30.0)
        self._raise_if_error()

    def cancel(self, *, terminate_process: bool = True) -> None:
        """Stop the writer and optionally terminate ffmpeg (export cancel)."""
        if self._closed and not self._thread.is_alive():
            return
        self._cancelled = True
        self._closed = True
        self._stop.set()
        self._drain_queue()
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        if terminate_process and self._enc.poll() is None:
            try:
                self._enc.terminate()
            except OSError:
                pass
        self._thread.join(timeout=2.0)
        if self._enc.poll() is None:
            try:
                self._enc.kill()
            except OSError:
                pass

    def stats(self) -> dict[str, float | int | None]:
        return {
            "framesSubmitted": self._frames_submitted,
            "framesWritten": self._frames_written,
            "queueSize": self._queue.maxsize,
            "packOnWriter": self._pack_fn is not None,
            "submitBlockP95Ms": _percentile(self._submit_block_times_ms, 95.0),
            "stdinBlockP95Ms": _percentile(self._stdin_block_times_ms, 95.0),
            "packAvgMs": (sum(self._pack_times_ms) / len(self._pack_times_ms)) if self._pack_times_ms else None,
            "packP95Ms": _percentile(self._pack_times_ms, 95.0),
            "submitBlockMaxMs": max(self._submit_block_times_ms) if self._submit_block_times_ms else None,
            "stdinBlockMaxMs": max(self._stdin_block_times_ms) if self._stdin_block_times_ms else None,
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
        close_stdin = False
        try:
            while True:
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                if item is _SENTINEL:
                    close_stdin = not self._cancelled
                    break
                payload = item
                if self._pack_fn is not None:
                    t_pack = time.perf_counter()
                    payload = self._pack_fn(item)  # type: ignore[arg-type]
                    self._pack_times_ms.append((time.perf_counter() - t_pack) * 1000.0)
                stdin = self._enc.stdin
                if stdin is None:
                    raise RuntimeError("FFmpeg stdin is not available")
                t0 = time.perf_counter()
                try:
                    stdin.write(payload)
                except (BrokenPipeError, OSError) as exc:
                    err_txt = _ffmpeg_err_text(self._enc, self._err_file)
                    raise RuntimeError(
                        f"FFmpeg pipe closed unexpectedly: {err_txt} (OS Error: {exc})"
                    ) from exc
                self._stdin_block_times_ms.append((time.perf_counter() - t0) * 1000.0)
                self._frames_written += 1
        except Exception as exc:
            self._error = exc
        finally:
            if close_stdin and self._enc.stdin is not None:
                try:
                    self._enc.stdin.close()
                except Exception:
                    pass
