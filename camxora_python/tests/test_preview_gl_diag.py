"""Tests for preview OpenGL diagnostic logging helpers."""

from __future__ import annotations

from pathlib import Path

from visualizer.preview_diag import (
    format_gl_context_info,
    preview_gl_diag_log_path,
    write_preview_gl_diag,
)


def test_preview_gl_diag_log_path_uses_localappdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = preview_gl_diag_log_path()
    assert path == tmp_path / "Camxora" / "logs" / "preview-gl-diag.log"


def test_write_preview_gl_diag_appends_to_appdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    write_preview_gl_diag("initializeGL ok", level="info", mirror_app_log=False)
    write_preview_gl_diag("Background texture uploaded: 10x10", level="info", mirror_app_log=False)
    path = preview_gl_diag_log_path()
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "initializeGL ok" in text
    assert "Background texture uploaded: 10x10" in text


def test_format_gl_context_info_reads_moderngl_fields() -> None:
    class _FakeCtx:
        version_code = 330
        info = {
            "GL_VENDOR": "TestVendor",
            "GL_RENDERER": "TestGPU",
            "GL_VERSION": "3.3.0",
        }

    info = format_gl_context_info(_FakeCtx())
    assert info["versionCode"] == "330"
    assert info["GL_VENDOR"] == "TestVendor"
    assert info["GL_RENDERER"] == "TestGPU"
    assert "frozen" in info
