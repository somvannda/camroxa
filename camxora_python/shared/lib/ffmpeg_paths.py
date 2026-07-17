"""Resolve FFmpeg/ffprobe for packaged and development desktop builds."""

from __future__ import annotations

import shutil
from pathlib import Path

from shared.lib.resource_paths import get_package_root
from shared.lib.runtime_paths import get_install_dir, is_frozen_runtime


def _candidate_ffmpeg_bins() -> list[Path]:
    names = ("ffmpeg.exe", "ffmpeg")
    roots: list[Path] = []
    install_dir = get_install_dir()
    if install_dir is not None:
        roots.append(install_dir)
        roots.append(install_dir / "_internal")
    roots.append(get_package_root())
    # Dev checkout: vendor/ next to camxora_python
    if not is_frozen_runtime():
        roots.append(Path(__file__).resolve().parents[2] / "vendor")

    candidates: list[Path] = []
    for root in roots:
        for folder in ("ffmpeg", "ffmpeg/bin", "bin"):
            for name in names:
                candidates.append(root / folder / name)
        for name in names:
            candidates.append(root / name)
    return candidates


def get_bundled_ffmpeg_path() -> str | None:
    for candidate in _candidate_ffmpeg_bins():
        try:
            if candidate.is_file():
                return str(candidate.resolve())
        except OSError:
            continue
    which = shutil.which("ffmpeg")
    return which


def resolve_ffmpeg_path(path_hint: str | None = None) -> str:
    """Prefer an existing user path, then bundled FFmpeg, then PATH."""
    candidate = str(path_hint or "").strip()
    if candidate:
        path = Path(candidate)
        if path.is_file():
            return str(path)
        if not candidate.lower().endswith(".exe"):
            exe_path = Path(f"{candidate}.exe")
            if exe_path.is_file():
                return str(exe_path)
    bundled = get_bundled_ffmpeg_path()
    if bundled:
        return bundled
    return candidate or "ffmpeg"


def resolve_ffprobe_path(ffmpeg_path: str | None = None) -> str:
    resolved = resolve_ffmpeg_path(ffmpeg_path)
    path = Path(resolved)
    sibling_names = ("ffprobe.exe", "ffprobe") if path.suffix.lower() == ".exe" else ("ffprobe", "ffprobe.exe")
    for name in sibling_names:
        sibling = path.with_name(name)
        if sibling.is_file():
            return str(sibling)
    which = shutil.which("ffprobe")
    return which or "ffprobe"
