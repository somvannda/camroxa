"""Validate Studio composition / projected project documents (doc 09)."""

from __future__ import annotations

from typing import Any

from features.studio.lib.scene_document import normalize_studio_document
from visualizer_studio.scene import NONE


def validate_composition_document(doc: Any) -> list[str]:
    """Return human-readable validation errors (empty = ok)."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["document must be an object"]
    scene = normalize_studio_document(doc)
    if not scene.get("composition"):
        errors.append("missing composition")
    comp = scene["composition"]
    for key in ("background", "spectrum", "logo", "particles", "lighting", "camera", "postProcessing", "audio"):
        if key not in comp:
            errors.append(f"composition missing {key}")
    shape = comp.get("spectrum", {}).get("shape")
    if shape in (None, "", NONE) and bool(comp.get("spectrum")):
        # allowed — spectrum off
        pass
    assets = scene.get("assets") if isinstance(scene.get("assets"), dict) else {}
    for role in ("backgroundImage", "logo", "audio"):
        if role not in assets:
            errors.append(f"assets missing {role}")
    return errors


def validate_project_document(project: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(project, dict):
        return ["project must be an object"]
    if project.get("schema") not in (None, "camxora.project"):
        # allow missing schema on drafts
        if project.get("schema"):
            errors.append(f"unsupported schema {project.get('schema')!r}")
    scenes = project.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("project requires scenes[]")
    else:
        main = scenes[0]
        if not isinstance(main, dict):
            errors.append("scenes[0] must be object")
        elif not isinstance(main.get("objects"), list):
            errors.append("scenes[0].objects must be a list")
    return errors
