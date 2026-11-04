"""Pipelined ffmpeg stdin writer — decouple render loop from slow pipe ingest (REQ-2.4)."""

from __future__ import annotations

import errno
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
_FINISH_JOIN_TIMEOUT_SEC = 30.0
_ERR_TAIL_CHARS = 2000

# Windows reports "the encoder closed its end of the pipe" as EINVAL (22) rather
# than EPIPE (32), so a BrokenPipeError-only check silently misdiagnoses it.
_PIPE_CLOSED_ERRNOS = frozenset({errno.EPIPE, errno.EINVAL})


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


def is_pipe_closed_error(exc: BaseException) -> bool:
    """True when ``exc`` means the encoder stopped reading our stdin pipe."""
    if isinstance(exc, BrokenPipeError):
        return True
    if isinstance(exc, OSError):
        return exc.errno in _PIPE_CLOSED_ERRNOS
    return False


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


def _ffmpeg_err_text(enc: Any, err_file: Any) -> str:
    """Back-compat alias — stderr text is only ever needed as a tail."""
    return ffmpeg_stderr_tail(err_file)


def _os_error_suffix(exc: BaseException) -> str:
    win = getattr(exc, "winerror", None)
    return f", winerror {win}" if win else ""


class PipelinedEncodeWriter:
    """Bounded queue + writer thread between render loop and ffmpeg stdin.

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
        size = resolve_encode_queue_size(queue_size)
        self._enc = enc
        self._err_file = err_file
        self._err_path = str(err_path or "").strip() or None
        self._pack_fn = pack_fn
        self._stop_on_clean_exit = bool(stop_on_clean_exit)
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=size)
        self._stop = threading.Event()
        self._cancelled = False
        self._error: Exception | None = None
        self._closed = False
        self._encoder_finished = False

        self._submit_block_times_ms: list[float] = []
        self._pack_times_ms: list[float] = []
        self._stdin_block_times_ms: list[float] = []
        self._frames_submitted = 0
        self._frames_written = 0
        self._frames_dropped = 0

        self._thread = threading.Thread(
            target=self._writer_loop,
            name="camxora-encode-writer",
            daemon=True,
        )
        self._thread.start()

    @property
    def encoder_finished(self) -> bool:
        """True when ffmpeg exited cleanly before the render loop finished."""
        return self._encoder_finished

    def submit(self, payload: Any) -> None:
        """Enqueue one frame payload; blocks when queue is full (back-pressure)."""
        self._raise_if_error()
        if self._closed:
            self._frames_dropped += 1
            return
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
        self._thread.join(timeout=_FINISH_JOIN_TIMEOUT_SEC)
        if self._thread.is_alive():
            # Writer is stuck inside a blocked pipe write. Kill the encoder so the
            # caller's ``enc.wait()`` cannot hang the export forever.
            self.cancel()
            raise RuntimeError(
                "Encode writer did not finish within "
                f"{_FINISH_JOIN_TIMEOUT_SEC:.0f}s "
                f"({self._frames_written}/{self._frames_submitted} frames written); "
                "FFmpeg was terminated"
            )
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

    def stats(self) -> dict[str, float | int | bool | None]:
        return {
            "framesSubmitted": self._frames_submitted,
            "framesWritten": self._frames_written,
            "framesDropped": self._frames_dropped,
            "encoderExitedEarly": self._encoder_finished,
            "queueSize": self._queue.maxsize,
            "packOnWriter": self._pack_fn is not None,
            "submitBlockP95Ms": _percentile(self._submit_block_times_ms, 95.0),
            "stdinBlockP95Ms": _percentile(self._stdin_block_times_ms, 95.0),
            "packAvgMs": (sum(self._pack_times_ms) / len(self._pack_times_ms)) if self._pack_times_ms else None,
            "packP95Ms": _percentile(self._pack_times_ms, 95.0),
            "submitBlockMaxMs": max(self._submit_block_times_ms) if self._submit_block_times_ms else None,
            "stdinBlockMaxMs": max(self._stdin_block_times_ms) if self._stdin_block_times_ms else None,
        }

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
        message = f"FFmpeg pipe closed unexpectedly: {detail} (OS Error: {exc}{_os_error_suffix(exc)})"
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
                if self._stop.is_set():
                    self._frames_dropped += 1
                    continue
                # Cheap liveness check: a frame written into a dead pipe is what
                # produced the confusing "[Errno 22] Invalid argument" reports.
                exit_code = self._encoder_exit_code()
                if exit_code is not None:
                    close_stdin = True
                    self._finish_on_encoder_exit(exit_code)
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
                    close_stdin = True
                    self._handle_write_failure(exc)
                    break
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
