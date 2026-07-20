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
