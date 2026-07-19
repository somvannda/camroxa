"""Application version exposed to update checks."""

from __future__ import annotations

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover - Python <3.11 fallback
    from importlib_metadata import PackageNotFoundError, version  # type: ignore[import-not-found]


def get_app_version() -> str:
    try:
        return version("camxora")
    except PackageNotFoundError:
        return "0.2.2"
