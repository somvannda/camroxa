"""Local workflow workspace persistence — filters and lane selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.lib.app_paths import get_workflow_workspace_prefs_path


@dataclass
class WorkflowWorkspacePrefs:
    from_date: str = ""
    to_date: str = ""
    active_only: bool = False
    selected_key: str = ""


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


class WorkflowLocalStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_workflow_workspace_prefs_path()

    def read_workspace_prefs(self) -> WorkflowWorkspacePrefs | None:
        raw = _read_json(self._path)
        if not isinstance(raw, dict):
            return None
        return WorkflowWorkspacePrefs(
            from_date=str(raw.get("fromDate") or "").strip(),
            to_date=str(raw.get("toDate") or "").strip(),
            active_only=bool(raw.get("activeOnly")),
            selected_key=str(raw.get("selectedKey") or "").strip(),
        )

    def write_workspace_prefs(self, prefs: WorkflowWorkspacePrefs) -> None:
        _write_json(
            self._path,
            {
                "version": 1,
                "fromDate": prefs.from_date,
                "toDate": prefs.to_date,
                "activeOnly": prefs.active_only,
                "selectedKey": prefs.selected_key,
            },
        )
        from shared.services.workspace_prefs_push import schedule_workspace_prefs_push

        schedule_workspace_prefs_push()
