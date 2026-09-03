"""Save/load a `ProjectState`'s `Project` to/from a JSON `.camxora` file.

This is a feature the reference `index.html` app doesn't have (it only stubs
undo/redo/save with "coming soon" toasts) — real persistence here reuses the
`Project`/`Track`/`Clip`/`MediaAsset` `to_dict`/`from_dict` round-trip already
required for undo/redo snapshots, so no separate serialization logic is
needed.

Media assets are referenced by absolute file path (like the timeline itself
already does); loading a project whose source media has moved/been deleted
still succeeds — affected clips simply fail to decode at render/playback
time (same failure mode as the browser original losing an in-memory blob).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from studio.core.models import Project
from studio.core.project_state import ProjectState

PROJECT_FILE_EXT = ".camxora"
PROJECT_FILE_FILTER = "Camxora project (*.camxora)"
_FORMAT_VERSION = 1


class ProjectLoadError(Exception):
    pass


def save_project(project_state: ProjectState, path: str | Path) -> Path:
    """Write `project_state.project` to `path` as formatted JSON. Overwrites
    any existing file. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "format_version": _FORMAT_VERSION,
        "project": project_state.project.to_dict(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_project(path: str | Path) -> ProjectState:
    """Read a `.camxora` JSON file and return a fresh `ProjectState` for it.

    Raises `ProjectLoadError` for missing/unreadable/malformed files rather
    than letting a raw `OSError`/`KeyError`/`json.JSONDecodeError` propagate,
    so UI callers can show one consistent error message."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectLoadError(f"Could not read project file: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProjectLoadError(f"Project file is not valid JSON: {exc}") from exc

    project_data = payload.get("project") if isinstance(payload, dict) else None
    if project_data is None:
        raise ProjectLoadError("Project file is missing its 'project' section.")

    try:
        project = Project.from_dict(project_data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectLoadError(f"Project file is malformed: {exc}") from exc

    state = ProjectState(project)
    state.recalc_duration()
    return state
