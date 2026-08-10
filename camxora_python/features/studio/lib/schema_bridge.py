"""Doc 09 schema bridge — project/scenes/objects projection over composition axes.

Authoring authority remains ``schema: camxora.composition``. This module exposes
a Project → Scenes → Objects → Components view for AI/plugins without requiring
a hard cut to ECS storage.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from features.studio.lib.scene_document import normalize_studio_document
from visualizer_studio.scene import NONE, default_document


def composition_to_project(doc: dict[str, Any]) -> dict[str, Any]:
    """Project composition axes into a doc-09-shaped document."""
    scene = normalize_studio_document(doc)
    comp = scene["composition"]
    assets = scene["assets"]
    project_id = str(scene.get("id") or f"project.{uuid4()}")
    name = str(scene.get("name") or "Untitled Composition")

    objects: list[dict[str, Any]] = [
        {
            "id": "obj.background",
            "type": "Background",
            "name": "Background",
            "enabled": bool(assets.get("backgroundImage") or comp["background"].get("image")),
            "components": [
                {
                    "type": "Background",
                    "properties": {
                        "image": assets.get("backgroundImage") or comp["background"].get("image"),
                        "motion": comp["background"].get("motion") or "static",
                        "atmosphere": comp["background"].get("atmosphere") or NONE,
                    },
                }
            ],
        },
        {
            "id": "obj.spectrum",
            "type": "Spectrum",
            "name": "Spectrum",
            "enabled": comp["spectrum"]["shape"] not in (None, "", NONE),
            "components": [
                {
                    "type": "Spectrum",
                    "properties": {
                        "shape": comp["spectrum"]["shape"],
                        "material": comp["spectrum"]["material"],
                        "animation": comp["spectrum"]["animation"],
                    },
                },
                {"type": "Material", "properties": {"material": comp["spectrum"]["material"]}},
                {"type": "Animation", "properties": {"type": comp["spectrum"]["animation"]}},
            ],
        },
        {
            "id": "obj.logo",
            "type": "Logo",
            "name": "Logo",
            "enabled": bool(comp["logo"].get("enabled", True)),
            "components": [
                {
                    "type": "Logo",
                    "properties": {
                        "path": assets.get("logo"),
                        "animation": comp["logo"].get("animation") or NONE,
                    },
                },
                {"type": "Animation", "properties": {"type": comp["logo"].get("animation") or NONE}},
            ],
        },
        {
            "id": "obj.text",
            "type": "Text",
            "name": "Text",
            "enabled": bool(comp["text"].get("enabled", False)),
            "components": [
                {
                    "type": "Text",
                    "properties": {
                        "albumEnabled": bool(scene.get("albumEnabled", False)),
                        "titleEnabled": bool(scene.get("titleEnabled", False)),
                        "albumManualText": str(scene.get("albumManualText") or ""),
                        "titleManualText": str(scene.get("titleManualText") or ""),
                    },
                }
            ],
        },
        {
            "id": "obj.overlay",
            "type": "Overlay",
            "name": "Overlay",
            "enabled": bool(comp["overlay"].get("enabled", False)),
            "components": [
                {
                    "type": "Overlay",
                    "properties": {"animation": comp["overlay"].get("animation") or NONE},
                }
            ],
        },
        {
            "id": "obj.particles",
            "type": "Particles",
            "name": "Particles",
            "enabled": comp["particles"]["type"] not in (None, "", NONE),
            "components": [
                {
                    "type": "Particles",
                    "properties": {
                        "type": comp["particles"]["type"],
                        "behavior": comp["particles"]["behavior"],
                    },
                }
            ],
        },
        {
            "id": "obj.lighting",
            "type": "Lighting",
            "name": "Lighting",
            "enabled": comp["lighting"].get("effect") not in (None, "", NONE),
            "components": [
                {
                    "type": "Lighting",
                    "properties": {
                        "effect": comp["lighting"].get("effect") or NONE,
                        "trigger": comp["lighting"].get("trigger") or NONE,
                    },
                },
                {
                    "type": "AudioReaction",
                    "properties": {
                        "channel": comp["lighting"].get("trigger") or NONE,
                        "target": "Lighting",
                    },
                },
            ],
        },
        {
            "id": "obj.camera",
            "type": "Camera",
            "name": "Camera",
            "enabled": comp["camera"].get("behavior") not in (None, "", NONE),
            "components": [
                {
                    "type": "Camera",
                    "properties": {"behavior": comp["camera"].get("behavior") or NONE},
                }
            ],
        },
        {
            "id": "obj.post",
            "type": "PostProcessing",
            "name": "Post Processing",
            "enabled": bool(comp["postProcessing"].get("effects")),
            "components": [
                {
                    "type": "PostProcessing",
                    "properties": {"effects": list(comp["postProcessing"].get("effects") or [])},
                }
            ],
        },
    ]

    mapping = dict(comp.get("audio", {}).get("mapping") or {})
    audio_bindings = [
        {"channel": bus, "target": target, "strength": 1.0}
        for target, bus in mapping.items()
        if bus not in (None, "", NONE)
    ]

    return {
        "schema": "camxora.project",
        "version": "1.0.0",
        "project": {
            "id": project_id,
            "name": name,
            "engineVersion": "1.0.0",
            "compositionSchema": "camxora.composition",
        },
        "settings": {},
        "assets": [
            {"role": "backgroundImage", "path": assets.get("backgroundImage")},
            {"role": "logo", "path": assets.get("logo")},
            {"role": "audio", "path": assets.get("audio")},
        ],
        "scenes": [
            {
                "id": "scene.main",
                "name": "Main Scene",
                "colorPalette": comp.get("colorPalette"),
                "objects": objects,
                "audioMapping": mapping,
                "audioBindings": audio_bindings,
                # Keep dual authority for round-trip fidelity.
                "composition": deepcopy(comp),
                "compositionAssets": deepcopy(assets),
            }
        ],
    }


def project_to_composition(project_doc: dict[str, Any]) -> dict[str, Any]:
    """Reduce a project-shaped document back to studio composition authority."""
    if not isinstance(project_doc, dict):
        return default_document()

    # Prefer embedded composition when present (lossless round-trip).
    scenes = project_doc.get("scenes")
    if isinstance(scenes, list) and scenes:
        main = scenes[0] if isinstance(scenes[0], dict) else {}
        if isinstance(main.get("composition"), dict):
            doc = default_document()
            doc["composition"] = deepcopy(main["composition"])
            if isinstance(main.get("compositionAssets"), dict):
                doc["assets"] = deepcopy(main["compositionAssets"])
            project = project_doc.get("project") if isinstance(project_doc.get("project"), dict) else {}
            doc["id"] = str(project.get("id") or main.get("id") or "")
            doc["name"] = str(project.get("name") or main.get("name") or "Untitled Composition")
            doc["templateName"] = doc["name"]
            return normalize_studio_document(doc)

    # Fallback: map objects → axes (best effort).
    doc = default_document()
    project = project_doc.get("project") if isinstance(project_doc.get("project"), dict) else {}
    doc["id"] = str(project.get("id") or "")
    doc["name"] = str(project.get("name") or "Untitled Composition")
    doc["templateName"] = doc["name"]
    if not isinstance(scenes, list) or not scenes:
        return normalize_studio_document(doc)

    main = scenes[0] if isinstance(scenes[0], dict) else {}
    objects = main.get("objects") if isinstance(main.get("objects"), list) else []
    comp = doc["composition"]
    assets = doc["assets"]
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        otype = str(obj.get("type") or "")
        components = obj.get("components") if isinstance(obj.get("components"), list) else []
        props: dict[str, Any] = {}
        for component in components:
            if isinstance(component, dict) and isinstance(component.get("properties"), dict):
                props.update(component["properties"])
        if otype == "Background":
            assets["backgroundImage"] = props.get("image")
            comp["background"]["image"] = props.get("image")
            comp["background"]["motion"] = props.get("motion") or "static"
            comp["background"]["atmosphere"] = props.get("atmosphere") or NONE
        elif otype == "Spectrum":
            comp["spectrum"]["shape"] = props.get("shape") or NONE
            comp["spectrum"]["material"] = props.get("material") or NONE
            comp["spectrum"]["animation"] = props.get("animation") or props.get("type") or NONE
        elif otype == "Logo":
            comp["logo"]["enabled"] = bool(obj.get("enabled", True))
            comp["logo"]["animation"] = props.get("animation") or props.get("type") or NONE
            assets["logo"] = props.get("path")
        elif otype == "Text":
            comp["text"]["enabled"] = bool(obj.get("enabled", False))
            doc["albumEnabled"] = bool(props.get("albumEnabled", False))
            doc["titleEnabled"] = bool(props.get("titleEnabled", False))
            doc["albumManualText"] = str(props.get("albumManualText") or "")
            doc["titleManualText"] = str(props.get("titleManualText") or "")
        elif otype == "Overlay":
            comp["overlay"]["enabled"] = bool(obj.get("enabled", False))
            comp["overlay"]["animation"] = props.get("animation") or NONE
        elif otype == "Particles":
            comp["particles"]["type"] = props.get("type") or NONE
            comp["particles"]["behavior"] = props.get("behavior") or NONE
        elif otype == "Lighting":
            comp["lighting"]["effect"] = props.get("effect") or NONE
            comp["lighting"]["trigger"] = props.get("trigger") or props.get("channel") or NONE
        elif otype == "Camera":
            comp["camera"]["behavior"] = props.get("behavior") or NONE
        elif otype == "PostProcessing":
            effects = props.get("effects")
            comp["postProcessing"]["effects"] = list(effects) if isinstance(effects, list) else []

    if isinstance(main.get("audioMapping"), dict):
        comp["audio"]["mapping"] = dict(main["audioMapping"])
    if main.get("colorPalette") is not None:
        comp["colorPalette"] = main.get("colorPalette")
    doc["composition"] = comp
    doc["assets"] = assets
    return normalize_studio_document(doc)
