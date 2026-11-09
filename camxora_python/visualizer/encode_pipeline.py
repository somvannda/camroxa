"""Pipelined encoder writers — decouple the render loop from slow encode ingest (REQ-2.4).

``BoundedFrameWriter`` owns the queue/writer-thread lifecycle shared by the ffmpeg
stdin writer (``PipelinedEncodeWriter``) and the native NVENC writer
(``NativeEncodeWriter``): back-pressure, cooperative cancel, error propagation to
the render thread, and dropped-frame accounting.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from shared.lib.pipe_errors import is_pipe_closed_error, os_error_suffix

_SENTINEL = object()
_DEFAULT_QUEUE_SIZE = 6
_MIN_QUEUE_SIZE = 2
_MAX_QUEUE_SIZE = 8
_FINISH_JOIN_TIMEOUT_SEC = 30.0
_ERR_TAIL_CHARS = 2000

# Windows reports "the encoder closed its end of the pipe" as EINVAL (22) rather
# than EPIPE (32); the classifier lives in shared.lib.pipe_errors.
__all__ = [
    "BoundedFrameWriter",
    "PipelinedEncodeWriter",
    "ffmpeg_stderr_tail",
    "is_pipe_closed_error",
    "pipelined_encode_enabled",
    "resolve_encode_queue_size",
]


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


def ffmpeg_stderr_tail(err_file: Any, *, max_chars: int = _ERR_TAIL_CHARS) -> str:
    """Tail of the encoder stderr log — best effort, never raises."""
    if err_file is None:
        return ""
    try:
        err_file.seek(0)
        text = str(err_file.read() or "").strip()
    except Exception:
        return ""
    return text[-int(max_chars) :] if max_chars else text


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(len(ordered) - 1, idx))
    return float(ordered[idx])


class BoundedFrameWriter:
    """Bounded frame queue + writer thread shared by the export encoders.

    Subclasses implement ``_consume(item)`` — write the payload to ffmpeg stdin or
    submit it to a native encoder — and may override the ``_on_*`` hooks. Keeping
    the lifecycle here means the ffmpeg and native paths cannot drift apart on
    cancel, error reporting, or dropped-frame accounting.
    """

    def __init__(
        self,
        *,
        queue_size: int | None = None,
        thread_name: str = "camxora-encode-writer",
        finish_join_timeout: float | None = None,
        copy_on_submit: bool = False,
    ) -> None:
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=resolve_encode_queue_size(queue_size))
        self._stop = threading.Event()
        self._cancelled = False
        self._closed = False
        self._error: Exception | None = None
        self._copy_on_submit = bool(copy_on_submit)
        # ``None`` resolves the module constant at call time (tests patch it).
        self._finish_join_timeout = finish_join_timeout

        self._submit_block_times_ms: list[float] = []
        self._frames_submitted = 0
        self._frames_written = 0
        self._frames_dropped = 0

        self._thread = threading.Thread(
            target=self._writer_loop,
            name=thread_name,
            daemon=True,
        )
        self._thread.start()

    # ── public API ───────────────────────────────────────────────────────────
    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def submit(self, payload: Any) -> None:
        """Enqueue one frame payload; blocks when queue is full (back-pressure)."""
        self._raise_if_error()
        if self._closed:
            self._frames_dropped += 1
            return
        if self._copy_on_submit:
            # Copy so a buffer pool (e.g. AsyncFramebufferReader) can reclaim it.
            payload = bytes(payload)
        t0 = time.perf_counter()
        while not self._closed:
            if self._stop.is_set():
                self._raise_if_error()
                self._frames_dropped += 1
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
        else:
            # The writer stopped while we were blocked on a full queue.
            self._frames_dropped += 1
            return
        self._submit_block_times_ms.append((time.perf_counter() - t0) * 1000.0)
        self._frames_submitted += 1

    def finish(self) -> None:
        """Drain queued frames, stop the writer, and surface any writer error."""
        if self._cancelled:
            # Cooperative cancel fired inside submit(); release the encoder too.
            self.cancel()
            return
        if self._closed:
            self._raise_if_error()
            return
        self._closed = True
        try:
            self._queue.put(_SENTINEL, timeout=1.0)
        except queue.Full:
            self._drain_queue()
            self._queue.put(_SENTINEL, timeout=1.0)
        self._thread.join(timeout=self._resolve_finish_timeout())
        if self._thread.is_alive():
            # Writer is stuck inside a blocked write. Kill the encoder so the
            # caller's ``wait()`` cannot hang the export forever.
            timeout = self._resolve_finish_timeout()
            self.cancel()
            raise RuntimeError(
                "Encode writer did not finish within "
                f"{timeout:.0f}s "
                f"({self._frames_written}/{self._frames_submitted} frames written); "
                "the encoder was terminated"
            )
        try:
            self._raise_if_error()
            self._after_finish()
        finally:
            self._cleanup()

    def cancel(self, *, terminate_process: bool = True) -> None:
        """Stop the writer and release the encoder (export cancel)."""
        if self._closed and not self._thread.is_alive():
            self._cleanup()
            return
        self._cancelled = True
        self._closed = True
        self._stop.set()
        self._drain_queue()
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            pass
        self._on_cancel(terminate_process)
        self._thread.join(timeout=2.0)
        self._on_cancel_joined()
        self._cleanup()

    def stats(self) -> dict[str, float | int | bool | None]:
        return {
            "framesSubmitted": self._frames_submitted,
            "framesWritten": self._frames_written,
            "framesDropped": self._frames_dropped,
            "queueSize": self._queue.maxsize,
            "submitBlockP95Ms": _percentile(self._submit_block_times_ms, 95.0),
            "submitBlockMaxMs": max(self._submit_block_times_ms) if self._submit_block_times_ms else None,
        }

    # ── subclass hooks ───────────────────────────────────────────────────────
    def _consume(self, item: Any) -> bool:
        """Handle one dequeued frame. Return False to stop consuming."""
        raise NotImplementedError

    def _on_sentinel(self) -> None:
        """Called when ``finish()``'s sentinel reaches the writer thread."""

    def _on_error(self) -> None:
        """Called after ``self._error`` is set by the writer thread."""

    def _finalize(self) -> None:
        """Always called when the writer thread exits."""

    def _on_cancel(self, terminate_process: bool) -> None:
        """Called before joining the writer during ``cancel()``."""

    def _on_cancel_joined(self) -> None:
        """Called after joining the writer during ``cancel()``."""

    def _after_finish(self) -> None:
        """Called after a clean ``finish()`` (drain the encoder)."""

    def _cleanup(self) -> None:
        """Called at the end of ``finish()``/``cancel()`` (release resources)."""

    # ── internals ────────────────────────────────────────────────────────────
    def _resolve_finish_timeout(self) -> float:
        if self._finish_join_timeout is not None:
            return float(self._finish_join_timeout)
        return float(_FINISH_JOIN_TIMEOUT_SEC)

    def _drain_queue(self) -> int:
        drained = 0
        while True:
            try:
                self._queue.get_nowait()
                drained += 1
            except queue.Empty:
                break
        return drained

    def _raise_if_error(self) -> None:
        if self._error is not None:
            raise self._error

    def _writer_loop(self) -> None:
        try:
            while True:
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    continue
                if item is _SENTINEL:
                    self._on_sentinel()
                    break
                if self._stop.is_set():
                    self._frames_dropped += 1
                    continue
                if self._consume(item) is False:
                    break
        except Exception as exc:
            self._error = exc
            self._on_error()
        finally:
            self._finalize()


class PipelinedEncodeWriter(BoundedFrameWriter):
    """ffmpeg stdin writer with an optional CPU packer on the writer thread.

    Optional ``pack_fn`` moves CPU packing (e.g. RGBA→NV12) onto the writer
    thread so the render loop only enqueues raw readback bytes.

    ``stop_on_clean_exit`` (default) treats an encoder that already exited 0 as a
    finished export: ffmpeg ends at the audio tail, so the last queued frames are
    dropped instead of crashing the render loop with a bogus broken-pipe error.
    """

    def __init__(
        self,
        enc: Any,
        *,
        queue_size: int | None = None,
        err_file: Any = None,
        pack_fn: Callable[[Any], Any] | None = None,
        err_path: str | None = None,
        stop_on_clean_exit: bool = True,
    ) -> None:
        self._enc = enc
        self._err_file = err_file
        self._err_path = str(err_path or "").strip() or None
        self._pack_fn = pack_fn
        self._stop_on_clean_exit = bool(stop_on_clean_exit)
        self._encoder_finished = False
        self._close_stdin = False
        self._pack_times_ms: list[float] = []
        self._stdin_block_times_ms: list[float] = []
        super().__init__(queue_size=queue_size, thread_name="camxora-encode-writer")

    @property
    def encoder_finished(self) -> bool:
        """True when ffmpeg exited cleanly before the render loop finished."""
        return self._encoder_finished

    def stats(self) -> dict[str, float | int | bool | None]:
        stats = super().stats()
        stats.update(
            {
                "encoderExitedEarly": self._encoder_finished,
                "packOnWriter": self._pack_fn is not None,
                "stdinBlockP95Ms": _percentile(self._stdin_block_times_ms, 95.0),
                "packAvgMs": (
                    (sum(self._pack_times_ms) / len(self._pack_times_ms))
                    if self._pack_times_ms
                    else None
                ),
                "packP95Ms": _percentile(self._pack_times_ms, 95.0),
                "stdinBlockMaxMs": (
                    max(self._stdin_block_times_ms) if self._stdin_block_times_ms else None
                ),
            }
        )
        return stats

    # ── writer hooks ─────────────────────────────────────────────────────────
    def _consume(self, item: Any) -> bool:
        # Cheap liveness check: a frame written into a dead pipe is what produced
        # the confusing "[Errno 22] Invalid argument" reports.
        exit_code = self._encoder_exit_code()
        if exit_code is not None:
            self._close_stdin = True
            self._finish_on_encoder_exit(exit_code)
            return False
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
            self._close_stdin = True
            self._handle_write_failure(exc)
            return False
        self._stdin_block_times_ms.append((time.perf_counter() - t0) * 1000.0)
        self._frames_written += 1
        return True

    def _on_sentinel(self) -> None:
        self._close_stdin = not self._cancelled

    def _finalize(self) -> None:
        if self._close_stdin and self._enc.stdin is not None:
            try:
                self._enc.stdin.close()
            except Exception:
                pass

    def _on_cancel(self, terminate_process: bool) -> None:
        if terminate_process and self._enc.poll() is None:
            try:
                self._enc.terminate()
            except OSError:
                pass

    def _on_cancel_joined(self) -> None:
        if self._enc.poll() is None:
            try:
                self._enc.kill()
            except OSError:
                pass

    # ── encoder diagnostics ──────────────────────────────────────────────────
    def _encoder_exit_code(self) -> int | None:
        try:
            return self._enc.poll()
        except Exception:
            return None

    def _encoder_exit_message(self, exit_code: int) -> str:
        detail = ffmpeg_stderr_tail(self._err_file) or (
            "no FFmpeg stderr output; the encoder stopped before all frames were written"
        )
        head = (
            f"FFmpeg exited (code {exit_code}) before the export finished "
            f"({self._frames_written}/{self._frames_submitted} frames written)"
        )
        message = f"{head}: {detail}"
        if self._err_path:
            message = f"{message} [stderr log: {self._err_path}]"
        return message

    def _pipe_closed_message(self, exc: OSError, err_txt: str) -> str:
        detail = err_txt or "no FFmpeg stderr output"
        message = f"FFmpeg pipe closed unexpectedly: {detail} (OS Error: {exc}{os_error_suffix(exc)})"
        if self._err_path:
            message = f"{message} [stderr log: {self._err_path}]"
        return message

    def _mark_nvenc_unavailable_if_needed(self, err_txt: str) -> None:
        try:
            from visualizer.nvenc_capability import (
                mark_nvenc_unavailable,
                nvenc_error_indicates_unavailable,
            )

            if nvenc_error_indicates_unavailable(err_txt):
                mark_nvenc_unavailable()
        except Exception:
            pass

    def _finish_on_encoder_exit(self, exit_code: int) -> None:
        """Encoder already stopped: a clean exit is the audio tail, not a crash.

        ffmpeg can end before the render loop pushed its last frames (it stops at
        the audio tail, or a real failure). Writing into that dead pipe used to
        raise ``OSError`` and abort the whole export with a "pipe closed
        unexpectedly" dialog. Exit 0 means the encoder produced its output, so
        stop the writer and count the dropped frames instead of failing the job.
        """
        if exit_code == 0 and self._stop_on_clean_exit:
            self._encoder_finished = True
            self._closed = True
            self._stop.set()
            self._frames_dropped += self._drain_queue()
            return
        raise RuntimeError(self._encoder_exit_message(exit_code))

    def _handle_write_failure(self, exc: OSError) -> None:
        exit_code = self._encoder_exit_code()
        if exit_code is not None:
            self._finish_on_encoder_exit(exit_code)
            return
        err_txt = ffmpeg_stderr_tail(self._err_file)
        self._mark_nvenc_unavailable_if_needed(err_txt)
        raise RuntimeError(self._pipe_closed_message(exc, err_txt)) from exc
