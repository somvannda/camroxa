"""Semantic version helpers for desktop update checks."""

from __future__ import annotations

import re

_VERSION_PATTERN = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def parse_version(value: str | None) -> tuple[int, int, int]:
    text = str(value or "").strip()
    if not text:
        return (0, 0, 0)
    match = _VERSION_PATTERN.match(text)
    if match is None:
        return (0, 0, 0)
    major = int(match.group(1) or 0)
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    return (major, minor, patch)


def is_remote_version_newer(current_version: str, remote_version: str) -> bool:
    return parse_version(remote_version) > parse_version(current_version)
