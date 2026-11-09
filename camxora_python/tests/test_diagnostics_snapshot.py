"""Local diagnostics snapshot: works while signed out, unlike the upload."""

from __future__ import annotations

from shared.services import log_sync


def test_write_diagnostics_snapshot(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        log_sync,
        "build_client_log_payload",
        lambda: {"content": "line one\nline two", "lineCount": 2},
    )

    path = log_sync.write_diagnostics_snapshot(tmp_path)

    assert path is not None
    assert path.exists()
    assert path.suffix == ".txt"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("Camxora diagnostics")
    assert "line one" in text


def test_write_diagnostics_snapshot_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(log_sync, "build_client_log_payload", lambda: None)

    assert log_sync.write_diagnostics_snapshot(tmp_path) is None
