"""Tests for native NVENC encode writer helper (REQ-3.5 export wiring)."""



from __future__ import annotations



from visualizer.native_encode_writer import (

    native_encode_dims_ok,

    native_encode_preferred,

    try_open_native_encode_writer,

)





def test_native_encode_preferred_default_off(monkeypatch) -> None:

    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE", raising=False)

    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE_EXPORT", raising=False)

    assert native_encode_preferred() is False





def test_native_encode_preferred_native_encode_flag(monkeypatch) -> None:

    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE", "1")

    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE_EXPORT", raising=False)

    assert native_encode_preferred() is True





def test_native_encode_preferred_export_override(monkeypatch) -> None:

    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE", raising=False)

    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE_EXPORT", "1")

    assert native_encode_preferred() is True





def test_native_encode_dims_ok() -> None:

    assert native_encode_dims_ok(256, 256) is True

    assert native_encode_dims_ok(1920, 1080) is True

    assert native_encode_dims_ok(128, 128) is False





def test_try_open_returns_none_when_disabled(monkeypatch, tmp_path) -> None:

    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE", raising=False)

    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE_EXPORT", raising=False)

    assert (

        try_open_native_encode_writer(

            width=640,

            height=360,

            fps=24,

            h264_path=str(tmp_path / "t.h264"),

        )

        is None

    )


# ── Lifecycle (shared BoundedFrameWriter base) ───────────────────────────────


class _FakeSession:
    """Minimal NativeEncodeSession stand-in — no GPU, no DLL."""

    def __init__(self, *, nv12: bool = False, fail: bool = False) -> None:
        self._nv12 = nv12
        self._fail = fail
        self.rgba_calls: list[tuple[int, int]] = []
        self.nv12_calls: list[tuple[int, int]] = []
        self.finished = 0
        self.exited = 0

    def supports_nv12(self) -> bool:
        return self._nv12

    def submit_rgba(self, data, stride: int) -> None:
        if self._fail:
            raise RuntimeError("nvenc submit failed")
        self.rgba_calls.append((len(data), int(stride)))

    def submit_nv12(self, data, width: int) -> None:
        if self._fail:
            raise RuntimeError("nvenc submit failed")
        self.nv12_calls.append((len(data), int(width)))

    def finish(self) -> None:
        self.finished += 1

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.exited += 1


def _writer(session: _FakeSession, *, width: int = 64, height: int = 64, tmp_path=None):
    from visualizer.native_encode_writer import NativeEncodeWriter

    return NativeEncodeWriter(
        session,
        h264_path=str(tmp_path / "out.h264") if tmp_path is not None else "out.h264",
        width=width,
        height=height,
        queue_size=2,
    )


def test_native_writer_submits_rgba_and_finishes_session(tmp_path) -> None:
    session = _FakeSession()
    writer = _writer(session, tmp_path=tmp_path)

    writer.submit(b"a" * (64 * 64 * 4))
    writer.submit(b"b" * (64 * 64 * 4))
    writer.finish()

    assert session.rgba_calls == [(64 * 64 * 4, 64 * 4)] * 2
    assert session.finished == 1
    assert session.exited == 1
    stats = writer.stats()
    assert stats["framesSubmitted"] == 2
    assert stats["framesEncoded"] == 2
    assert stats["framesDropped"] == 0
    assert stats["backend"] == "native_nvenc"
    assert stats["submitNv12"] is False
    assert "framesWritten" not in stats


def test_native_writer_packs_nv12_when_session_supports_it(tmp_path, monkeypatch) -> None:
    class _FakePacker:
        def __init__(self, width, height, fmt) -> None:
            self.width = width
            self.height = height
            self.fmt = fmt
            self.calls = 0

        def __call__(self, _raw):
            self.calls += 1
            return b"nv12"

    import visualizer.readback as readback

    monkeypatch.setattr(readback, "PipeFramePacker", _FakePacker)
    session = _FakeSession(nv12=True)
    writer = _writer(session, tmp_path=tmp_path)
    writer.submit(b"a" * (64 * 64 * 4))
    writer.finish()

    assert session.nv12_calls == [(4, 64)]
    assert session.rgba_calls == []
    assert writer.stats()["submitNv12"] is True


def test_native_writer_propagates_session_error_and_exits(tmp_path) -> None:
    import pytest

    session = _FakeSession(fail=True)
    writer = _writer(session, tmp_path=tmp_path)
    writer.submit(b"a" * (64 * 64 * 4))
    with pytest.raises(RuntimeError, match="nvenc submit failed"):
        writer.finish()

    assert session.exited == 1
    assert session.finished == 0


def test_native_writer_cancel_releases_session(tmp_path) -> None:
    session = _FakeSession()
    writer = _writer(session, tmp_path=tmp_path)
    writer.submit(b"a" * (64 * 64 * 4))
    writer.cancel()

    assert session.exited >= 1
    assert writer.closed is True
    assert writer.cancelled is True


