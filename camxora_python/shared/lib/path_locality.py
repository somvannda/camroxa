"""Detect paths that belong to a different Windows user profile.

Account-wide settings can replay ``C:\\Users\\Alice\\...`` onto Bob's machine.
Those paths are never creatable (Access Denied walking up to Alice's profile),
so callers must reject them *before* ``mkdir`` — otherwise every settings
touch and startup floods the log with multi-level PermissionError cascades.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Windows profile folders that are shared across users, not a single account.
_SHARED_WINDOWS_PROFILE_NAMES = frozenset(
    {
        "public",
        "default",
        "default user",
        "all users",
        "defaultapppool",
    }
)

_USERS_SEGMENT = re.compile(r"(?i)^(?:[a-zA-Z]:[/\\]|\\\\[^\\]+\\[^\\]+[/\\])Users[/\\]")


def current_windows_profile_name() -> str | None:
    """Leaf name of this process's Windows user profile, or None if unknown."""
    for candidate in (
        os.environ.get("USERPROFILE"),
        os.environ.get("HOME"),
        str(Path.home()),
    ):
        text = str(candidate or "").strip()
        if not text:
            continue
        name = Path(text).name.strip()
        if name:
            return name
    return None


def windows_profile_name_from_path(path: str) -> str | None:
    """If ``path`` is under ``...\\Users\\<name>\\...``, return ``<name>``.

    Handles normal drive paths (``C:\\Users\\Alice\\...``) and UNC profiles
    (``\\\\server\\Users\\Alice\\...``). Returns None when the path is not
    under a Users profile folder.
    """
    text = str(path or "").strip()
    if not text:
        return None
    normalized = text.replace("/", "\\")
    match = _USERS_SEGMENT.match(normalized)
    if not match:
        return None
    rest = normalized[match.end() :]
    if not rest:
        return None
    profile = rest.split("\\", 1)[0].strip()
    return profile or None


def is_foreign_windows_profile_path(path: str) -> bool:
    """True when ``path`` lives under another Windows user's profile folder.

    Same-machine paths under the current profile, shared profiles (Public),
    and non-Users paths (``D:\\Music``, ``E:\\SUNO``) return False.
    """
    if os.name != "nt":
        return False
    profile = windows_profile_name_from_path(path)
    if not profile:
        return False
    if profile.casefold() in _SHARED_WINDOWS_PROFILE_NAMES:
        return False
    current = current_windows_profile_name()
    if not current:
        return False
    return profile.casefold() != current.casefold()
