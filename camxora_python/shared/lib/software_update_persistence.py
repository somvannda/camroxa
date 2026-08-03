"""Persist mandatory software-update state across app restarts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.lib.runtime_paths import get_updates_work_dir

logger = logging.getLogger(__name__)

PENDING_FILENAME = "pending-update.json"
STATUS_FILENAME = "update-status.json"

# Helper script phases written to update-status.json
PHASE_WAITING = "waiting"
PHASE_INSTALLING = "installing"
PHASE_VERIFYING = "verifying"
PHASE_DONE = "done"
PHASE_FAILED = "failed"

_ACTIVE_PHASES = frozenset({PHASE_WAITING, PHASE_INSTALLING, PHASE_VERIFYING})


@dataclass(slots=True)
class PersistedSoftwareUpdate:
    version: str
    download_url: str
    mandatory: bool
    release_notes: str
    notification_id: str
    install_in_progress: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "download_url": self.download_url,
            "mandatory": self.mandatory,
            "release_notes": self.release_notes,
            "notification_id": self.notification_id,
            "install_in_progress": self.install_in_progress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PersistedSoftwareUpdate | None:
        version = str(raw.get("version") or "").strip()
        if not version:
            return None
        return cls(
            version=version,
            download_url=str(raw.get("download_url") or "").strip(),
            mandatory=bool(raw.get("mandatory")),
            release_notes=str(raw.get("release_notes") or "").strip(),
            notification_id=str(raw.get("notification_id") or "").strip(),
            install_in_progress=bool(raw.get("install_in_progress")),
        )


@dataclass(slots=True)
class UpdateHelperStatus:
    phase: str
    exit_code: int = 0
    installed_version: str = ""
    error: str = ""

    @property
    def is_active(self) -> bool:
        return self.phase in _ACTIVE_PHASES

    @property
    def is_done(self) -> bool:
        return self.phase == PHASE_DONE

    @property
    def is_failed(self) -> bool:
        return self.phase == PHASE_FAILED

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> UpdateHelperStatus | None:
        phase = str(raw.get("phase") or "").strip().lower()
        if not phase:
            return None
        try:
            exit_code = int(raw.get("exit_code") or 0)
        except (TypeError, ValueError):
            exit_code = 0
        return cls(
            phase=phase,
            exit_code=exit_code,
            installed_version=str(raw.get("installed_version") or "").strip(),
            error=str(raw.get("error") or "").strip(),
        )


def pending_update_path() -> Path:
    return get_updates_work_dir() / PENDING_FILENAME


def update_status_path() -> Path:
    return get_updates_work_dir() / STATUS_FILENAME


def load_pending_update() -> PersistedSoftwareUpdate | None:
    path = pending_update_path()
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return None
    return PersistedSoftwareUpdate.from_dict(raw)


def save_pending_update(state: PersistedSoftwareUpdate) -> None:
    path = pending_update_path()
    try:
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    except OSError:
        logger.exception("Failed to persist pending software update")


def clear_pending_update() -> None:
    _unlink_quiet(pending_update_path())


def load_update_status() -> UpdateHelperStatus | None:
    raw = _read_json(update_status_path())
    if not isinstance(raw, dict):
        return None
    return UpdateHelperStatus.from_dict(raw)


def clear_update_status() -> None:
    _unlink_quiet(update_status_path())


def clear_all_update_markers() -> None:
    clear_pending_update()
    clear_update_status()


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Ignoring unreadable update state file: %s", path)
        return None


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Unable to remove update state file: %s", path)
