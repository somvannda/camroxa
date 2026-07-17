"""Local image workspace persistence — date filters and queue selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.lib.app_paths import get_image_workspace_prefs_path


@dataclass
class ImageWorkspacePrefs:
    from_date: str = ""
    to_date: str = ""
    selected_queue_key: str = ""


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


class ImageLocalStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_image_workspace_prefs_path()

    def read_workspace_prefs(self) -> ImageWorkspacePrefs | None:
        raw = _read_json(self._path)
        if not isinstance(raw, dict):
            return None
        return ImageWorkspacePrefs(
            from_date=str(raw.get("fromDate") or "").strip(),
            to_date=str(raw.get("toDate") or "").strip(),
            selected_queue_key=str(raw.get("selectedQueueKey") or "").strip(),
        )

    def write_workspace_prefs(self, prefs: ImageWorkspacePrefs) -> None:
        _write_json(
            self._path,
            {
                "version": 1,
                "fromDate": prefs.from_date,
                "toDate": prefs.to_date,
                "selectedQueueKey": prefs.selected_queue_key,
            },
        )
        from shared.services.workspace_prefs_push import schedule_workspace_prefs_push

        schedule_workspace_prefs_push()
