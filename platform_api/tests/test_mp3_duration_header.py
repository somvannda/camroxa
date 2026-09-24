"""Tests for MP3 Xing/Info duration-header normalization."""

from __future__ import annotations

from types import SimpleNamespace

from platform_api.services import mp3_duration_header as mod

_HEADERLESS_MP3 = b"ID3\x04\x00\x00" + b"\x00" * 512
_HEADED_MP3 = b"ID3\x04\x00\x00" + b"\x00" * 180 + b"Xing" + b"\x00" * 512
_FTYP = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 300


def test_mp3_has_duration_header() -> None:
    assert mod.mp3_has_duration_header(_HEADERLESS_MP3) is False
    assert mod.mp3_has_duration_header(_HEADED_MP3) is True
    assert mod.mp3_has_duration_header(b"ID3" + b"\x00" * 180 + b"Info" + b"\x00" * 20) is True


def test_looks_like_mpeg_audio() -> None:
    assert mod.looks_like_mpeg_audio(_HEADERLESS_MP3) is True
    assert mod.looks_like_mpeg_audio(b"\xff\xfb\x90\x00" + b"\x00" * 100) is True
    assert mod.looks_like_mpeg_audio(_FTYP) is False
    assert mod.looks_like_mpeg_audio(b"") is False
    assert mod.looks_like_mpeg_audio(b"RIFF") is False


def test_ensure_returns_non_mpeg_unchanged() -> None:
    assert mod.ensure_mp3_duration_header(_FTYP) == _FTYP
    assert mod.ensure_mp3_duration_header(b"") == b""


def test_ensure_noop_when_header_present() -> None:
    assert mod.ensure_mp3_duration_header(_HEADED_MP3) == _HEADED_MP3


def test_ensure_keeps_original_when_ffmpeg_missing(monkeypatch) -> None:
    monkeypatch.setattr(mod, "resolve_ffmpeg_path", lambda: "")
    assert mod.ensure_mp3_duration_header(_HEADERLESS_MP3) == _HEADERLESS_MP3


def test_ensure_remuxes_headerless_mp3(monkeypatch) -> None:
    monkeypatch.setattr(mod, "resolve_ffmpeg_path", lambda: "ffmpeg")

    def _fake_run(cmd, **kwargs):  # noqa: ANN001, ARG001
        out_path = cmd[-1]
        with open(out_path, "wb") as handle:
            handle.write(b"ID3\x04\x00\x00" + b"\x00" * 180 + b"Xing" + b"\x00" * 512)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    normalized = mod.ensure_mp3_duration_header(_HEADERLESS_MP3)
    assert mod.mp3_has_duration_header(normalized) is True


def test_ensure_keeps_original_when_remux_fails(monkeypatch) -> None:
    monkeypatch.setattr(mod, "resolve_ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stderr=b"boom", stdout=b""),
    )
    assert mod.ensure_mp3_duration_header(_HEADERLESS_MP3) == _HEADERLESS_MP3


async def test_ensure_async_noop_for_headed() -> None:
    assert await mod.ensure_mp3_duration_header_async(_HEADED_MP3) == _HEADED_MP3
