"""Free-disk-space checks for workspace/output/download folders.

A folder can pass a plain ``mkdir`` + ``is_dir()`` check while still being
useless for real work — e.g. a near-full USB/recovery drive, or a synced
account-level path that happened to land on a small secondary drive on this
machine. Callers that are about to write real media files (MP3/MP4/image
downloads, exports) should also check free space, not just existence.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# A single track download or export scratch write easily needs tens of MB.
# This floor is intentionally conservative — it exists to catch drives that
# are *obviously* unusable (a few KB/MB free), not to enforce a real quota.
MIN_FREE_BYTES_WORKSPACE = 200 * 1024 * 1024  # 200 MB


def get_free_bytes(path: str | Path) -> int | None:
    """Free space (bytes) on the drive containing ``path``.

    Walks up to the nearest existing ancestor so this works even for a path
    that doesn't exist yet. Returns None if it can't be determined (e.g. an
    unreachable network path) — callers should treat unknown as "don't block".
    """
    normalized = str(path or "").strip()
    if not normalized:
        return None
    candidate = Path(normalized)
    for probe in (candidate, *candidate.parents):
        try:
            if probe.exists():
                return shutil.disk_usage(str(probe)).free
        except OSError:
            return None
    return None


def has_sufficient_free_space(path: str | Path, minimum_bytes: int = MIN_FREE_BYTES_WORKSPACE) -> bool:
    """True if the drive containing ``path`` has at least ``minimum_bytes`` free.

    Unknown/undetectable free space is treated as sufficient — this check is
    meant to steer away from *known*-bad drives, not to block on things that
    can't be measured (e.g. some network shares).
    """
    free = get_free_bytes(path)
    if free is None:
        return True
    return free >= minimum_bytes
