"""Local music workspace persistence — dates, channels, prompt selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.lib.app_paths import get_music_workspace_prefs_path


@dataclass
class MusicWorkspacePrefs:
    from_date: str = ""
    to_date: str = ""
    primary_profile_ids: list[str] | None = None
    secondary_profile_ids: list[str] | None = None
    selected_description_id: str = ""
    selected_structure_id: str = ""


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


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or None


class MusicLocalStore:
    """Read/write last-used music workspace layout on this machine."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_music_workspace_prefs_path()

    def read_workspace_prefs(self) -> MusicWorkspacePrefs | None:
        raw = _read_json(self._path)
        if not isinstance(raw, dict):
            return None
        return MusicWorkspacePrefs(
            from_date=str(raw.get("fromDate") or "").strip(),
            to_date=str(raw.get("toDate") or "").strip(),
            primary_profile_ids=_string_list(raw.get("primaryProfileIds")),
            secondary_profile_ids=_string_list(raw.get("secondaryProfileIds")),
            selected_description_id=str(raw.get("selectedDescriptionId") or "").strip(),
            selected_structure_id=str(raw.get("selectedStructureId") or "").strip(),
        )

    def write_workspace_prefs(self, prefs: MusicWorkspacePrefs) -> None:
        payload = {
            "version": 1,
            "fromDate": prefs.from_date,
            "toDate": prefs.to_date,
            "primaryProfileIds": list(prefs.primary_profile_ids or []),
            "secondaryProfileIds": list(prefs.secondary_profile_ids or []),
            "selectedDescriptionId": prefs.selected_description_id,
            "selectedStructureId": prefs.selected_structure_id,
        }
        _write_json(self._path, payload)
        from shared.services.workspace_prefs_push import schedule_workspace_prefs_push

        schedule_workspace_prefs_push()
