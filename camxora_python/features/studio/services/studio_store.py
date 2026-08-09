"""Local Studio project persistence — separate from VideoLocalStore."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from features.studio.lib.scene_document import blank_studio_document, normalize_studio_document
from shared.lib.app_paths import get_studio_prefs_path, get_studio_projects_dir


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class StudioStore:
    def __init__(self, user_id: str | None = None) -> None:
        self._user_id = user_id
        self._projects_dir = get_studio_projects_dir(user_id)
        self._prefs_path = get_studio_prefs_path(user_id)
        self._projects_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[tuple[str, str]]:
        """Return (id, name) sorted by updated time desc."""
        rows: list[tuple[str, str, str]] = []
        for path in self._projects_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            pid = str(data.get("id") or path.stem)
            name = str(data.get("name") or data.get("templateName") or pid)
            updated = str(data.get("updatedAt") or "")
            rows.append((pid, name, updated))
        rows.sort(key=lambda item: item[2], reverse=True)
        return [(pid, name) for pid, name, _ in rows]

    def read_prefs(self) -> dict[str, Any]:
        if not self._prefs_path.is_file():
            return {}
        try:
            data = json.loads(self._prefs_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def write_prefs(self, prefs: dict[str, Any]) -> None:
        self._prefs_path.parent.mkdir(parents=True, exist_ok=True)
        self._prefs_path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")

    def active_project_id(self) -> str | None:
        prefs = self.read_prefs()
        value = prefs.get("projectId")
        return str(value) if value else None

    def set_active_project_id(self, project_id: str | None) -> None:
        prefs = self.read_prefs()
        if project_id:
            prefs["projectId"] = project_id
        else:
            prefs.pop("projectId", None)
        self.write_prefs(prefs)

    def _project_path(self, project_id: str) -> Path:
        safe = "".join(ch for ch in project_id if ch.isalnum() or ch in "-_")
        return self._projects_dir / f"{safe}.json"

    def load_project(self, project_id: str) -> dict[str, Any] | None:
        path = self._project_path(project_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        doc = normalize_studio_document(raw)
        doc["id"] = project_id
        return doc

    def save_project(self, doc: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_studio_document(doc)
        project_id = str(normalized.get("id") or "").strip() or str(uuid.uuid4())
        normalized["id"] = project_id
        normalized["updatedAt"] = _now()
        if not normalized.get("createdAt"):
            normalized["createdAt"] = normalized["updatedAt"]
        path = self._project_path(project_id)
        path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        self.set_active_project_id(project_id)
        return normalized

    def create_project(self, *, name: str = "Untitled Composition") -> dict[str, Any]:
        doc = blank_studio_document(name=name)
        doc["id"] = str(uuid.uuid4())
        return self.save_project(doc)

    def load_active_or_create(self) -> dict[str, Any]:
        active = self.active_project_id()
        if active:
            loaded = self.load_project(active)
            if loaded is not None:
                return loaded
        return self.create_project()
