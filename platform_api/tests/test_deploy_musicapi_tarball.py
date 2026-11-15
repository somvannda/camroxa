"""The musicapi tarball must ship LF text so it cannot fake deploy drift."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import tarfile


def _load():
    path = Path(__file__).resolve().parents[2] / "scripts" / "deploy" / "sync_musicapi_sandbox.py"
    spec = importlib.util.spec_from_file_location("musicapi_deploy", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_tarball(path: Path, members: dict[str, bytes]) -> None:
    import io

    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def _read_tarball(path: Path) -> dict[str, bytes]:
    with tarfile.open(path, "r:gz") as tar:
        return {
            member.name: tar.extractfile(member).read()  # type: ignore[union-attr]
            for member in tar
            if member.isfile()
        }


def test_normalize_tarball_text_rewrites_windows_line_endings(tmp_path: Path) -> None:
    archive = tmp_path / "src.tar.gz"
    _write_tarball(
        archive,
        {
            "scripts/deploy/backup-offhost.py": b"print(1)\r\nprint(2)\r\n",
            "musicapi/src/client.ts": b"const a = 1;\r\n",
            "musicapi/public/cover.png": b"\x89PNG\r\n\x1a\nbinary",
        },
    )

    _load().normalize_tarball_text(archive)

    members = _read_tarball(archive)
    assert members["scripts/deploy/backup-offhost.py"] == b"print(1)\nprint(2)\n"
    assert members["musicapi/src/client.ts"] == b"const a = 1;\n"
    # Binary payloads are never rewritten.
    assert members["musicapi/public/cover.png"] == b"\x89PNG\r\n\x1a\nbinary"


def test_normalize_tarball_text_leaves_lf_files_alone(tmp_path: Path) -> None:
    archive = tmp_path / "src.tar.gz"
    _write_tarball(archive, {"musicapi/package.json": b'{"name":"x"}\n'})

    _load().normalize_tarball_text(archive)

    assert _read_tarball(archive)["musicapi/package.json"] == b'{"name":"x"}\n'
