"""Application version exposed to update checks and the shell footer."""

from __future__ import annotations

import re
from pathlib import Path

try:
    from importlib.metadata import PackageNotFoundError, version as pkg_version
except ImportError:  # pragma: no cover - Python <3.11 fallback
    from importlib_metadata import PackageNotFoundError, version as pkg_version  # type: ignore[import-not-found]

from shared.lib.runtime_paths import get_install_dir, is_frozen_runtime

_DEFAULT_VERSION = "0.3.0"
_MODULE_ROOT = Path(__file__).resolve().parents[2]


def _read_version_file(path: Path) -> str | None:
    try:
        # PowerShell Set-Content -Encoding utf8 writes a UTF-8 BOM. That BOM is
        # invisible in the UI but breaks semver parsing (version becomes 0.0.0).
        value = path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    if value.lower().startswith("v") and len(value) > 1 and value[1].isdigit():
        value = value[1:].strip()
    return value or None


def _read_pyproject_version() -> str | None:
    pyproject = _MODULE_ROOT / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip() or None


def _bundled_version_paths() -> list[Path]:
    paths: list[Path] = []
    install_dir = get_install_dir()
    if install_dir is not None:
        paths.extend(
            (
                install_dir / "_internal" / "resources" / "app-version.txt",
                install_dir / "resources" / "app-version.txt",
            )
        )
    if is_frozen_runtime():
        import sys

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            paths.append(Path(meipass) / "resources" / "app-version.txt")
    paths.append(_MODULE_ROOT / "resources" / "app-version.txt")
    return paths


def get_app_version() -> str:
    """Return the desktop app version.

    Packaged builds must read the build-stamped ``resources/app-version.txt`` file.
    ``importlib.metadata`` is unreliable inside PyInstaller bundles because stale
    ``camxora-*.dist-info`` entries from the build machine can report old versions.
    """
    if is_frozen_runtime():
        for path in _bundled_version_paths():
            bundled = _read_version_file(path)
            if bundled:
                return bundled
        return _DEFAULT_VERSION

    pyproject_version = _read_pyproject_version()
    if pyproject_version:
        return pyproject_version

    try:
        return pkg_version("camxora")
    except PackageNotFoundError:
        return _DEFAULT_VERSION
