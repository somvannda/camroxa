"""Renderer bridge — composition document → GPU draw dict."""

from __future__ import annotations

from typing import Any

from visualizer_studio.composition_effects.gpu_bridge import apply_gpu_preview_bridge
from visualizer_studio.scene import CompositionContractError, Scene, load_scene, require_composition_document
from visualizer_studio.scene.compile import CompiledFrame, compile_scene


def document_to_renderer_dict(
    doc: dict[str, Any],
    *,
    time_sec: float = 0.0,
    audio_level: float = 0.0,
) -> dict[str, Any]:
    """Fail-closed: requires composition; returns compiled GPU payload."""
    scene = load_scene(doc)
    compiled = compile_scene(scene, time_sec=time_sec, audio_level=audio_level)
    return apply_gpu_preview_bridge(compiled.to_renderer_dict(), source_doc=doc if isinstance(doc, dict) else None)


def merge_workspace_assets(doc: dict[str, Any], workspace: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach workspace media paths into assets without legacy domain bags."""
    out = dict(doc) if isinstance(doc, dict) else {}
    assets = dict(out.get("assets") or {})
    ws = workspace if isinstance(workspace, dict) else {}
    logo = str(ws.get("logoPath") or assets.get("logo") or "").strip()
    bg = str(ws.get("backgroundPath") or ws.get("previewBackground") or assets.get("backgroundImage") or "").strip()
    audio = str(ws.get("selectedMp3Path") or ws.get("activeTrackPath") or assets.get("audio") or "").strip()
    if logo:
        assets["logo"] = logo
    if bg:
        assets["backgroundImage"] = bg
    if audio:
        assets["audio"] = audio
    out["assets"] = assets
    if "composition" not in out or not isinstance(out.get("composition"), dict):
        raise CompositionContractError("merge_workspace_assets requires composition")
    out.setdefault("schema", "camxora.composition")
    return out


__all__ = (
    "CompiledFrame",
    "CompositionContractError",
    "Scene",
    "apply_gpu_preview_bridge",
    "compile_scene",
    "document_to_renderer_dict",
    "load_scene",
    "merge_workspace_assets",
    "require_composition_document",
)
