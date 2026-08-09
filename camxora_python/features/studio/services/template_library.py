"""Local Studio Template Library (PRD) — save/duplicate/import/export."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from features.studio.lib.scene_document import normalize_studio_document
from features.studio.lib.schema_bridge import composition_to_project, project_to_composition
from shared.lib.app_paths import get_studio_projects_dir


def get_studio_templates_dir(user_id: str | None = None) -> Path:
    root = get_studio_projects_dir(user_id).parent / "studio-templates"
    root.mkdir(parents=True, exist_ok=True)
    return root


class StudioTemplateLibrary:
    def __init__(self, user_id: str | None = None) -> None:
        self._dir = get_studio_templates_dir(user_id)
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[tuple[str, str]]:
        self._dir.mkdir(parents=True, exist_ok=True)
        rows: list[tuple[str, str, str]] = []
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            tid = str(data.get("templateId") or path.stem)
            name = str(data.get("name") or tid)
            updated = str(data.get("updatedAt") or "")
            rows.append((tid, name, updated))
        rows.sort(key=lambda r: r[2], reverse=True)
        return [(a, b) for a, b, _ in rows]

    def save_template(self, doc: dict[str, Any], *, name: str | None = None) -> dict[str, Any]:
        scene = normalize_studio_document(doc)
        tid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "templateId": tid,
            "name": name or str(scene.get("name") or "Template"),
            "version": "1.0.0",
            "createdAt": now,
            "updatedAt": now,
            "composition": scene,
            "project": composition_to_project(scene),
        }
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{tid}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def load_template(self, template_id: str) -> dict[str, Any] | None:
        path = self._dir / f"{template_id}.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        if isinstance(data.get("composition"), dict):
            return normalize_studio_document(data["composition"])
        if isinstance(data.get("project"), dict):
            return project_to_composition(data["project"])
        return None

    def duplicate(self, template_id: str) -> dict[str, Any] | None:
        loaded = self.load_template(template_id)
        if loaded is None:
            return None
        loaded["name"] = f"{loaded.get('name') or 'Template'} Copy"
        return self.save_template(loaded, name=str(loaded["name"]))

    def export_template(self, template_id: str, dest: str | Path) -> Path:
        src = self._dir / f"{template_id}.json"
        out = Path(dest)
        shutil.copy2(src, out)
        return out

    def import_template(self, src: str | Path) -> dict[str, Any]:
        data = json.loads(Path(src).read_text(encoding="utf-8"))
        if isinstance(data.get("composition"), dict):
            return self.save_template(data["composition"], name=str(data.get("name") or "Imported"))
        if isinstance(data.get("project"), dict):
            return self.save_template(project_to_composition(data["project"]), name=str(data.get("name") or "Imported"))
        return self.save_template(normalize_studio_document(data), name="Imported")
