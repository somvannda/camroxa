"""Effect pack app version matching — port of effectPackVersioning.ts."""

from __future__ import annotations

import re


def normalize_app_version(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _compare_versions(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    for index in range(3):
        delta = left[index] - right[index]
        if delta != 0:
            return delta
    return 0


def matches_app_version_range(app_version: str, version_range: str) -> bool:
    normalized_range = str(version_range or "*").strip()
    if not normalized_range or normalized_range == "*":
        return True

    version = normalize_app_version(app_version)
    if version is None:
        return False

    if normalized_range.startswith("^"):
        base = normalize_app_version(normalized_range[1:])
        if base is None:
            return False
        return version[0] == base[0] and _compare_versions(version, base) >= 0

    if normalized_range.startswith("~"):
        base = normalize_app_version(normalized_range[1:])
        if base is None:
            return False
        return version[0] == base[0] and version[1] == base[1] and _compare_versions(version, base) >= 0

    exact = normalize_app_version(normalized_range)
    if exact is None:
        return False
    return _compare_versions(version, exact) == 0
