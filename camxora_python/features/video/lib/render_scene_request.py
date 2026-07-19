"""Render scene request builders — port of renderSceneRequest.ts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_RESOLUTION = "1920x1080"
# Export FPS (preview paints at 60). Default 24 for speed; UI offers 30/48/60.
DEFAULT_EXPORT_FPS = 24
PIPELINE_EXPORT_FPS = 24
EXPORT_FPS_CHOICES = (24, 30, 48, 60)
REEL_EXPORT_RESOLUTION = "1080x1920"
MIN_VALID_EXPORT_BYTES = 50_000


def normalize_export_fps(value: object, *, default: int = DEFAULT_EXPORT_FPS) -> int:
    """Clamp export FPS to the supported UI choices."""
    try:
        fps = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        fps = int(default)
    if fps in EXPORT_FPS_CHOICES:
        return fps
    # Nearest supported choice (keeps legacy/odd settings usable).
    return min(EXPORT_FPS_CHOICES, key=lambda choice: abs(choice - fps))


@dataclass(frozen=True)
class RenderSceneAssets:
    background_path: str | None
    logo_path: str | None
    audio_path: str | None
    run_dir: str | None = None


@dataclass(frozen=True)
class RenderSceneOutput:
    resolution: str
    width: int
    height: int
    fps: int


@dataclass(frozen=True)
class RenderSceneContext:
    template_id: str | None
    branch: str | None
    batch_id: str | None
    role: str | None
    draft_source: str


@dataclass(frozen=True)
class ManualRenderSceneRequest:
    mode: str
    template: dict[str, Any]
    draft: dict[str, Any]
    assets: RenderSceneAssets
    output: RenderSceneOutput
    context: RenderSceneContext


@dataclass(frozen=True)
class PipelineRenderSceneRequest:
    mode: str
    template: dict[str, Any]
    draft: dict[str, Any]
    assets: RenderSceneAssets
    output: RenderSceneOutput
    context: RenderSceneContext


def parse_render_resolution(resolution: str) -> tuple[int, int]:
    match = re.match(r"^(\d+)\s*x\s*(\d+)$", str(resolution or "").strip(), re.IGNORECASE)
    if not match:
        return 1920, 1080
    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        return 1920, 1080
    return width, height


def build_video_render_output_settings(resolution: str, fps: int = DEFAULT_EXPORT_FPS) -> RenderSceneOutput:
    normalized = str(resolution or DEFAULT_OUTPUT_RESOLUTION).strip() or DEFAULT_OUTPUT_RESOLUTION
    width, height = parse_render_resolution(normalized)
    safe_fps = normalize_export_fps(fps)
    return RenderSceneOutput(
        resolution=normalized,
        width=width,
        height=height,
        fps=safe_fps,
    )


def build_manual_render_scene_request(
    *,
    template: dict[str, Any],
    template_draft: dict[str, Any],
    workspace: dict[str, Any],
    background_path: str | None = None,
    selected_mp3_path: str | None = None,
    fps: int = DEFAULT_EXPORT_FPS,
) -> ManualRenderSceneRequest:
    logo_path = str(template_draft.get("logoPath") or workspace.get("logoPath") or "").strip() or None
    audio_path = str(selected_mp3_path or workspace.get("selectedMp3Path") or "").strip() or None
    bg_path = str(background_path or workspace.get("backgroundPath") or "").strip() or None
    output = build_video_render_output_settings(str(workspace.get("outputResolution") or DEFAULT_OUTPUT_RESOLUTION), fps)
    return ManualRenderSceneRequest(
        mode="manual",
        template=template,
        draft=template_draft,
        assets=RenderSceneAssets(
            background_path=bg_path,
            logo_path=logo_path,
            audio_path=audio_path,
            run_dir=None,
        ),
        output=output,
        context=RenderSceneContext(
            template_id=str(workspace.get("templateId") or "").strip() or None,
            branch=None,
            batch_id=None,
            role=None,
            draft_source="live",
        ),
    )


def resolve_manual_export_output_dir(*, settings: dict[str, Any], audio_path: str) -> str:
    configured = str(settings.get("videoRenderOutputDir") or "").strip()
    if configured:
        return configured
    audio = str(audio_path or "").strip()
    if audio:
        return str(Path(audio).parent)
    return str(Path.home() / "Videos")


def build_manual_export_output_path(*, audio_path: str, output_dir: str) -> str:
    stem = Path(audio_path).stem if audio_path else "manual-export"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return str(Path(output_dir) / f"{stem}_CAMXORA_{stamp}.mp4")


def build_pipeline_render_scene_request(
    *,
    template: dict[str, Any],
    workspace: dict[str, Any],
    run_dir: str,
    background_path: str,
    branch: str,
    batch_id: str,
    role: str,
    selected_mp3_path: str | None = None,
    fps: int = PIPELINE_EXPORT_FPS,
) -> PipelineRenderSceneRequest:
    from features.video.lib.video_template_draft import build_video_template_draft

    draft = build_video_template_draft(
        template,
        logo_path=str(workspace.get("logoPath") or ""),
        # Preview-only template background must never feed pipeline assets.
        background_path="",
    )
    audio_path = str(selected_mp3_path or workspace.get("selectedMp3Path") or "").strip() or None
    resolution = REEL_EXPORT_RESOLUTION if branch == "reel" else str(workspace.get("outputResolution") or DEFAULT_OUTPUT_RESOLUTION)
    output = build_video_render_output_settings(resolution, fps)
    return PipelineRenderSceneRequest(
        mode="pipeline",
        template=template,
        draft=draft,
        assets=RenderSceneAssets(
            # Always the batch AI background from progress meta — never template previewBackground.
            background_path=str(background_path or "").strip() or None,
            logo_path=str(workspace.get("logoPath") or "").strip() or None,
            audio_path=audio_path,
            run_dir=str(run_dir or "").strip() or None,
        ),
        output=output,
        context=RenderSceneContext(
            template_id=str(workspace.get("templateId") or "").strip() or None,
            branch=branch,
            batch_id=str(batch_id or "").strip() or None,
            role=str(role or "").strip() or None,
            draft_source="saved",
        ),
    )


def is_valid_export_output(target_path: str) -> bool:
    path = Path(str(target_path or "").strip())
    try:
        return path.is_file() and path.stat().st_size > MIN_VALID_EXPORT_BYTES
    except OSError:
        return False


def build_pipeline_long_output_path(*, mp3_path: str, output_dir: str) -> str:
    stem = Path(mp3_path).stem if mp3_path else "export"
    return str(Path(output_dir) / f"{stem}.mp4")


def build_pipeline_export_output_path(*, mp3_path: str, output_dir: str, branch: str) -> str:
    long_path = build_pipeline_long_output_path(mp3_path=mp3_path, output_dir=output_dir)
    if branch == "reel":
        stem = Path(mp3_path).stem if mp3_path else "export"
        return str(Path(output_dir) / f"{stem}_REEL.mp4")
    return long_path
