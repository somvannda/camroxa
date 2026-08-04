from __future__ import annotations

from pathlib import Path

from platform_api.utils.upload_paths import (
    project_root,
    resolve_upload_path,
    upload_path_exists,
    uploads_root,
)


def test_resolve_upload_path_accepts_relative_under_uploads(tmp_path, monkeypatch):
    root = tmp_path
    uploads = root / "uploads"
    uploads.mkdir()
    target = uploads / "logos" / "a.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"png")

    monkeypatch.setattr("platform_api.utils.upload_paths.project_root", lambda: root)
    resolved = resolve_upload_path("uploads/logos/a.png")
    assert resolved == target.resolve()
    assert upload_path_exists("uploads/logos/a.png") is True


def test_resolve_upload_path_rejects_outside_uploads(tmp_path, monkeypatch):
    root = tmp_path
    (root / "uploads").mkdir()
    outside = root / "secrets.txt"
    outside.write_text("nope", encoding="utf-8")

    monkeypatch.setattr("platform_api.utils.upload_paths.project_root", lambda: root)
    assert resolve_upload_path(str(outside)) is None
    assert upload_path_exists(str(outside)) is False


def test_upload_path_exists_false_when_missing(tmp_path, monkeypatch):
    root = tmp_path
    (root / "uploads").mkdir()
    monkeypatch.setattr("platform_api.utils.upload_paths.project_root", lambda: root)
    assert upload_path_exists("uploads/logos/missing.png") is False


def test_project_and_uploads_root_shape():
    assert uploads_root() == (project_root() / "uploads").resolve()
