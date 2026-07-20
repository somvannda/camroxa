"""Tests for cooperative export cancel flag files."""

from __future__ import annotations

from features.video.lib.export_cancel import (
    CANCEL_ENV,
    clear_export_cancel,
    export_cancel_requested,
    new_cancel_path,
    request_export_cancel,
)


def test_cancel_flag_roundtrip(tmp_path, monkeypatch) -> None:
    path = str(tmp_path / "cancel.flag")
    monkeypatch.setenv(CANCEL_ENV, path)
    assert export_cancel_requested() is False
    request_export_cancel(path)
    assert export_cancel_requested() is True
    assert export_cancel_requested(path) is True
    clear_export_cancel(path)
    assert export_cancel_requested(path) is False


def test_new_cancel_path_is_unique() -> None:
    a = new_cancel_path()
    b = new_cancel_path()
    assert a != b
    assert "camxora_export_cancel_" in a
