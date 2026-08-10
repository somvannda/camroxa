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
    normalize_export_fps,
)
from shared.lib.export_codec import normalize_export_speed_mode
from visualizer_studio.composition_renderer import document_to_renderer_dict


def export_project_json(doc: dict[str, Any], path: str | Path) -> Path:
    """Write doc-09 project projection to disk."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = composition_to_project(doc)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def studio_export_options(doc: dict[str, Any]) -> dict[str, Any]:
    scene = normalize_studio_document(doc)
    export = scene.get("studioExport") if isinstance(scene.get("studioExport"), dict) else {}
    return {
        "resolution": str(export.get("resolution") or "1920x1080"),
        "fps": normalize_export_fps(export.get("fps") or 24),
        "quality": normalize_export_speed_mode(export.get("quality") or "fast"),
        "includeAudio": bool(export.get("includeAudio", True)),
        "rangeStart": float(export.get("rangeStart") or 0.0),
        "rangeEnd": float(export.get("rangeEnd") or 0.0),
    }


def studio_export_readiness(doc: dict[str, Any]) -> tuple[bool, str]:
    scene = normalize_studio_document(doc)
    assets = scene["assets"]
    audio = str(assets.get("audio") or "").strip()
    background = str(assets.get("backgroundImage") or "").strip()
    background_video = str(assets.get("backgroundVideo") or "").strip()
    if not audio:
        return False, "Select an audio track before exporting video."
    if not background and not background_video:
        return False, "Select a background image or video plate before exporting video."
    if not Path(audio).is_file():
        return False, "Audio path is missing on disk."
    if background and not Path(background).is_file():
        return False, "Background path is missing on disk."
    if background_video and not Path(background_video).is_file():
        return False, "Background video path is missing on disk."
    if not background and background_video:
        # Manual export worker still requires an image plate path today.
        return False, "Export currently needs a still background image (video plate is preview-only)."
    opts = studio_export_options(scene)
    end = float(opts["rangeEnd"])
    start = float(opts["rangeStart"])
    if end > 0 and end <= start:
        return False, "Export range end must be greater than start (or 0 for full track)."
    return True, ""


def build_studio_manual_export_request(
    doc: dict[str, Any],
    *,
    resolution: str | None = None,
    fps: int | None = None,
    output_dir: str = "",
    quality: str | None = None,
) -> ManualRenderSceneRequest:
    """Build a ManualRenderSceneRequest from a Studio composition document.

    Does not touch VideoLocalStore / Music pipeline prefs.
    """
    scene = normalize_studio_document(doc)
    opts = studio_export_options(scene)
    res = str(resolution or opts["resolution"])
    out_fps = normalize_export_fps(fps if fps is not None else opts["fps"])
    speed = normalize_export_speed_mode(quality or opts["quality"])
    rendered = document_to_renderer_dict(scene)
    # Keep composition on template for engine-true export.
    template = dict(rendered)
    template["schema"] = "camxora.composition"
    template["composition"] = scene["composition"]
    template["assets"] = scene["assets"]
    template["studioExport"] = {
        **opts,
        "resolution": res,
        "fps": out_fps,
        "quality": speed,
        "outputDir": output_dir or "",
    }
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
        output=build_video_render_output_settings(res, out_fps),
        context=RenderSceneContext(
            template_id=str(scene.get("id") or None),
            branch="studio",
            batch_id=None,
            role="studio",
            draft_source="studio",
        ),
    )
