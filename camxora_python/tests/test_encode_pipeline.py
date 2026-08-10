"""Unit tests for pipelined ffmpeg stdin writer (REQ-2.4)."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from visualizer_video.encode_pipeline import (
    PipelinedEncodeWriter,
    _percentile,
    pipelined_encode_enabled,
    resolve_encode_queue_size,
)


class _SlowStdin:
    def __init__(self, delay_sec: float = 0.05) -> None:
        self.delay_sec = delay_sec
        self.chunks: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        time.sleep(self.delay_sec)
        self.chunks.append(bytes(data))

    def close(self) -> None:
        self.closed = True


class _MockProcess:
    def __init__(self, stdin: _SlowStdin | None = None) -> None:
        self.stdin = stdin or _SlowStdin()
        self._returncode: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = -15

    def kill(self) -> None:
        self.killed = True
        self._returncode = -9


def test_pipelined_encode_enabled_env_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_PIPELINED_ENCODE", "1")
    assert pipelined_encode_enabled() is True
    monkeypatch.setenv("CAMXORA_PIPELINED_ENCODE", "0")
    assert pipelined_encode_enabled() is False


def test_percentile_empty_and_single() -> None:
    assert _percentile([], 95.0) is None
    assert _percentile([4.0], 95.0) == 4.0


def test_finish_drains_queue_and_closes_stdin() -> None:
    proc = _MockProcess(_SlowStdin(delay_sec=0.0))
    writer = PipelinedEncodeWriter(proc, queue_size=2)
    writer.submit(b"frame-a")
    writer.submit(b"frame-b")
    writer.finish()

    assert proc.stdin.chunks == [b"frame-a", b"frame-b"]
    assert proc.stdin.closed is True
    stats = writer.stats()
    assert stats["framesSubmitted"] == 2
    assert stats["framesWritten"] == 2


def test_back_pressure_when_queue_full() -> None:
    proc = _MockProcess(_SlowStdin(delay_sec=0.1))
    writer = PipelinedEncodeWriter(proc, queue_size=2)

    submit_started = time.perf_counter()
    writer.submit(b"f1")
    writer.submit(b"f2")
    writer.submit(b"f3")
    writer.submit(b"f4")
    submit_elapsed = time.perf_counter() - submit_started

    assert submit_elapsed >= 0.08
    writer.finish()
    assert len(proc.stdin.chunks) == 4
    assert writer.stats()["submitBlockP95Ms"] is not None


def test_cancel_terminates_process_and_joins_quickly() -> None:
    proc = _MockProcess(_SlowStdin(delay_sec=0.2))
    writer = PipelinedEncodeWriter(proc, queue_size=2)
    writer.submit(b"frame")
    started = time.perf_counter()
    writer.cancel()
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0
    assert proc.terminated or proc.killed


def test_writer_error_propagates_to_render_thread() -> None:
    class _BrokenStdin:
        def write(self, _data: bytes) -> None:
            raise BrokenPipeError("pipe closed")

        def close(self) -> None:
            return

    proc = SimpleNamespace(stdin=_BrokenStdin(), poll=lambda: None)
    writer = PipelinedEncodeWriter(proc, queue_size=2, err_file=None)
    writer.submit(b"frame")
    with pytest.raises(RuntimeError, match="FFmpeg pipe closed unexpectedly"):
        writer.finish()


def test_queue_maxsize_is_clamped() -> None:
    proc = _MockProcess(_SlowStdin(delay_sec=0.0))
    writers = [
        PipelinedEncodeWriter(proc, queue_size=1),
        PipelinedEncodeWriter(proc, queue_size=2),
        PipelinedEncodeWriter(proc, queue_size=6),
        PipelinedEncodeWriter(proc, queue_size=99),
    ]
    try:
        assert writers[0]._queue.maxsize == 2
        assert writers[1]._queue.maxsize == 2
        assert writers[2]._queue.maxsize == 6
        assert writers[3]._queue.maxsize == 8
    finally:
        for writer in writers:
            writer.cancel(terminate_process=False)


def test_resolve_encode_queue_size_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_ENCODE_QUEUE", raising=False)
    assert resolve_encode_queue_size() == 6
    monkeypatch.setenv("CAMXORA_ENCODE_QUEUE", "4")
    assert resolve_encode_queue_size() == 4
    monkeypatch.setenv("CAMXORA_ENCODE_QUEUE", "99")
    assert resolve_encode_queue_size() == 8


def test_pack_fn_runs_on_writer_thread() -> None:
    proc = _MockProcess(_SlowStdin(delay_sec=0.0))
    seen: list[bytes] = []

    def _pack(raw: bytes) -> bytes:
        seen.append(raw)
        return b"packed-" + raw

    writer = PipelinedEncodeWriter(proc, queue_size=2, pack_fn=_pack)
    writer.submit(b"rgba")
    writer.finish()
    assert seen == [b"rgba"]
    assert proc.stdin.chunks == [b"packed-rgba"]
    stats = writer.stats()
    assert stats["packOnWriter"] is True
    assert stats["packAvgMs"] is not None
