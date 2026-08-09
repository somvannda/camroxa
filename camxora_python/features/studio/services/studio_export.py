"""Studio export helpers — JSON project bridge + manual GPU export request."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from features.studio.lib.scene_document import normalize_studio_document
from features.studio.lib.schema_bridge import composition_to_project
from features.video.lib.render_scene_request import (
    ManualRenderSceneRequest,
    RenderSceneAssets,
    RenderSceneContext,
    build_video_render_output_settings,
)
from visualizer.composition_renderer import document_to_renderer_dict


def export_project_json(doc: dict[str, Any], path: str | Path) -> Path:
    """Write doc-09 project projection to disk."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = composition_to_project(doc)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def studio_export_readiness(doc: dict[str, Any]) -> tuple[bool, str]:
    scene = normalize_studio_document(doc)
    assets = scene["assets"]
    audio = str(assets.get("audio") or "").strip()
    background = str(assets.get("backgroundImage") or "").strip()
    if not audio:
        return False, "Select an audio track before exporting video."
    if not background:
        return False, "Select a background image before exporting video."
    if not Path(audio).is_file():
        return False, "Audio path is missing on disk."
    if not Path(background).is_file():
        return False, "Background path is missing on disk."
    return True, ""


def build_studio_manual_export_request(
    doc: dict[str, Any],
    *,
    resolution: str = "1920x1080",
    fps: int = 24,
    output_dir: str = "",
) -> ManualRenderSceneRequest:
    """Build a ManualRenderSceneRequest from a Studio composition document.

    Does not touch VideoLocalStore / Music pipeline prefs.
    """
    scene = normalize_studio_document(doc)
    rendered = document_to_renderer_dict(scene)
    # Keep composition on template for engine-true export.
    template = dict(rendered)
    template["schema"] = "camxora.composition"
    template["composition"] = scene["composition"]
    template["assets"] = scene["assets"]
    assets = scene["assets"]
    return ManualRenderSceneRequest(
        mode="manual",
        template=template,
        draft={},
        assets=RenderSceneAssets(
            background_path=str(assets.get("backgroundImage") or "") or None,
            logo_path=str(assets.get("logo") or "") or None,
            audio_path=str(assets.get("audio") or "") or None,
        ),
        output=build_video_render_output_settings(resolution, fps),
        context=RenderSceneContext(
            template_id=str(scene.get("id") or None),
            branch="studio",
            batch_id=None,
            role="studio",
            draft_source="studio",
        ),
    )
