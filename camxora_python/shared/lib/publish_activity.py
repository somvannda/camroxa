"""Live upload activity shared by every publish worker and the Progress table.

An upload is started either from the Progress row menu or by the pipeline after
a merge. Rows only knew about the second kind through the server (a job row),
which does not exist until the file has finished transferring - so a 2.6 GB
transfer had no per-row status at all and several of them could run at once with
no way to tell which video was moving.

This registry is the single source of truth for "what is uploading right now":
keyed by batch/channel/role, it holds the stage, byte progress, and the worker so
the row can show its own percentage and cancel its own transfer.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

STAGE_STORAGE = "storage"
STAGE_PROVIDER = "provider"

_lock = threading.Lock()
_activity: dict[str, "UploadActivity"] = {}
_workers: dict[str, object] = {}


@dataclass(slots=True)
class UploadActivity:
    key: str
    label: str = ""
    stage: str = STAGE_STORAGE
    sent: int = 0
    total: int = 0
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def percent(self) -> int:
        if self.total <= 0:
            return 0
        return max(0, min(100, int(self.sent * 100 / self.total)))

    def describe(self) -> str:
        """Short cell text: the only honest signal while a file is in flight."""
        if self.stage == STAGE_PROVIDER:
            return f"Uploading {_elapsed(self.started_at)}"
        if self.total > 0:
            return f"Storage {self.percent}%"
        return "Uploading"


def _elapsed(started_at: float) -> str:
    seconds = max(0.0, time.time() - float(started_at or 0))
    if seconds < 60:
        return "<1m"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours, rest = divmod(minutes, 60)
    return f"{hours}h {rest}m" if rest else f"{hours}h"


def slot_key(batch_id: object, profile_id: object, role: object) -> str:
    return (
        f"{str(batch_id or '').strip()}:"
        f"{str(profile_id or '').strip()}:"
        f"{str(role or '').strip().upper()}"
    )


def begin(
    key: str,
    *,
    label: str = "",
    total: int = 0,
    worker: object | None = None,
) -> None:
    if not key.strip(":"):
        return
    with _lock:
        _activity[key] = UploadActivity(
            key=key, label=label, stage=STAGE_STORAGE, total=max(0, int(total))
        )
        if worker is not None:
            _workers[key] = worker


def progress(key: str, sent: int, total: int) -> None:
    with _lock:
        item = _activity.get(key)
        if item is None:
            return
        item.sent = max(0, int(sent))
        item.total = max(item.total, int(total))
        item.updated_at = time.time()


def mark_provider(key: str) -> None:
    """The file is out of our storage; the provider is uploading to YouTube."""
    with _lock:
        item = _activity.get(key)
        if item is None:
            return
        item.stage = STAGE_PROVIDER
        item.sent = item.total
        item.updated_at = time.time()


def finish(key: str) -> None:
    with _lock:
        _activity.pop(key, None)
        _workers.pop(key, None)


def snapshot(key: str) -> UploadActivity | None:
    with _lock:
        item = _activity.get(key)
        return item


def describe(key: str) -> str:
    item = snapshot(key)
    return item.describe() if item is not None else ""


def active() -> list[UploadActivity]:
    with _lock:
        return list(_activity.values())


def cancel(key: str) -> bool:
    """Ask the worker that owns this slot to stop (safe from the UI thread)."""
    with _lock:
        worker = _workers.get(key)
    request = getattr(worker, "requestInterruption", None)
    if request is None:
        return False
    try:
        request()
    except Exception:
        return False
    return True
