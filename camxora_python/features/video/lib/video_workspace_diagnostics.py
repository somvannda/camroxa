"""Video workspace diagnostics builder — port of useVideoWorkspaceDiagnostics.ts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from features.video.lib.pipeline_inputs import ResolvedVideoPipelineInputs
from shared.models.desktop import VideoPlaybackState, VideoWorkspaceState

DiagnosticsTone = Literal["neutral", "ready", "warning", "running"]


@dataclass(frozen=True)
class DiagnosticsBadge:
    label: str
    tone: DiagnosticsTone


@dataclass(frozen=True)
class DiagnosticsDomainItem:
    label: str
    dirty: bool


@dataclass(frozen=True)
class PreviewGuidance:
    title: str
    detail: str
    items: tuple[str, ...]
    tone: DiagnosticsTone
    visible: bool


@dataclass(frozen=True)
class VideoWorkspaceDiagnosticsViewModel:
    preview_status_label: str
    preview_status_message: str
    preview_status_tone: DiagnosticsTone
    preview_guidance_title: str
    preview_guidance_detail: str
    preview_guidance_items: tuple[str, ...]
    preview_guidance_tone: DiagnosticsTone
    preview_needs_attention: bool
    save_status_label: str
    save_status_tone: DiagnosticsTone
    export_status_label: str
    export_status_tone: DiagnosticsTone
    pipeline_status_label: str
    pipeline_status_tone: DiagnosticsTone
    template_id: str
    branch_label: str
    background_label: str
    track_label: str
    performance_label: str
    dirty_domains: tuple[DiagnosticsDomainItem, ...]
    can_reset_local_draft: bool


def _format_path(value: str | None, fallback: str) -> str:
    trimmed = str(value or "").strip()
    return trimmed or fallback


def _build_preview_guidance(
    *,
    preview_lifecycle_status: str,
    preview_lifecycle_message: str,
    preview_remount_pending: bool,
    background_path: str,
    preview_track_path: str,
    pipeline_inputs: ResolvedVideoPipelineInputs | None,
    gpu_preview_available: bool,
) -> PreviewGuidance:
    if preview_remount_pending:
        return PreviewGuidance(
            title="Preview recovery in progress",
            detail="The GPU preview surface is remounting after an explicit recovery action.",
            items=(
                "Wait a moment before judging the current frame output.",
                "Refresh Workspace if the stage context looks stale after recovery.",
                "Copy Diagnostics if repeated remounts are still required.",
            ),
            tone="running",
            visible=True,
        )

    if not gpu_preview_available:
        from shared.lib.runtime_paths import is_frozen_runtime

        if is_frozen_runtime():
            items = (
                "You can still edit templates and settings without live preview.",
                "Reinstall Camxora from the latest installer (GPU libraries are bundled in the app).",
                "Copy Diagnostics and contact support if this PC still cannot start preview.",
            )
        else:
            items = (
                "You can still edit templates, drafts, and export settings without live preview.",
                "For local development, run: pip install -e .",
                "Packaged Camxora.exe already bundles GPU libraries — end users never run pip.",
            )
        return PreviewGuidance(
            title="Live GPU preview is unavailable in this environment",
            detail="The graphics stack used for ModernGL preview did not load.",
            items=items,
            tone="warning",
            visible=True,
        )

    status = str(preview_lifecycle_status or "running").strip().lower()
    message = str(preview_lifecycle_message or "").strip()
    if status == "error":
        return PreviewGuidance(
            title="The GPU preview failed to start cleanly",
            detail=message or "The preview surface reported an initialization error.",
            items=(
                "Use Remount Preview to retry GPU initialization.",
                "Refresh Workspace if assets were changed immediately before the failure.",
                "Copy Diagnostics when the same startup error keeps returning.",
            ),
            tone="warning",
            visible=True,
        )
    if status == "initializing":
        return PreviewGuidance(
            title="Preview startup is still in progress",
            detail=message or "The preview is loading assets or initializing OpenGL.",
            items=(
                "Wait for audio analysis and GL init to finish before checking fine details.",
                "The shell remains editable while preview startup completes.",
            ),
            tone="running",
            visible=True,
        )
    if status == "fallback-active":
        items = ["Edits still apply to the local workspace draft while degraded preview guidance is active."]
        if not str(background_path or "").strip():
            items.append("Select a background to replace the empty stage with real artwork.")
        if not str(preview_track_path or "").strip():
            items.append("Select a preview MP3 so the stage can validate audio-reactive motion.")
        if pipeline_inputs is not None and not pipeline_inputs.ready:
            items.append("Choose a pipeline run when you need export-ready branch context.")
        return PreviewGuidance(
            title="Preview is running with missing stage assets",
            detail=message or "Attach background and preview audio for full compositor validation.",
            items=tuple(items),
            tone="warning",
            visible=True,
        )

    return PreviewGuidance(
        title="",
        detail="",
        items=(),
        tone="ready",
        visible=False,
    )


def build_video_workspace_diagnostics(
    *,
    workspace: VideoWorkspaceState | None,
    template_name_draft: str,
    workspace_dirty: bool,
    draft_dirty_map: dict[str, bool],
    active_domain_tab: str,
    saving: bool,
    playback: VideoPlaybackState | None,
    preview_track_path: str,
    pipeline_branch: str,
    pipeline_inputs: ResolvedVideoPipelineInputs | None,
    preview_lifecycle_status: str,
    preview_lifecycle_message: str,
    preview_remount_pending: bool,
    gpu_preview_available: bool,
    performance: dict[str, Any] | None = None,
    export_gate_active: int = 0,
    export_gate_limit: int = 1,
) -> VideoWorkspaceDiagnosticsViewModel:
    playback = playback or VideoPlaybackState()
    background_path = str(workspace.background_path if workspace else "").strip()
    branch_label = "Long 16:9" if pipeline_branch != "reel" else "Reel 9:16"

    if preview_remount_pending:
        preview_status = DiagnosticsBadge("Preview Recovering", "running")
    elif not gpu_preview_available:
        preview_status = DiagnosticsBadge("GPU Preview Unavailable", "warning")
    elif preview_lifecycle_status == "error":
        preview_status = DiagnosticsBadge("Preview Error", "warning")
    elif preview_lifecycle_status == "initializing" or playback.is_loading:
        preview_status = DiagnosticsBadge("Preview Loading", "running")
    elif playback.is_playing:
        preview_status = DiagnosticsBadge("Preview Playing", "running")
    elif playback.is_ready:
        preview_status = DiagnosticsBadge("Preview Ready", "ready")
    elif not preview_track_path.strip():
        preview_status = DiagnosticsBadge("No Preview Track", "neutral")
    else:
        preview_status = DiagnosticsBadge("Preview Waiting", "warning")

    preview_messages = {
        "Preview Recovering": "GPU preview is remounting the OpenGL compositor.",
        "GPU Preview Unavailable": "The live preview graphics stack failed to load.",
        "Preview Error": preview_lifecycle_message or "Preview initialization failed.",
        "Preview Loading": "Preview transport or analysis is still loading.",
        "Preview Playing": "Preview playback is active.",
        "Preview Ready": "Preview transport is ready.",
        "No Preview Track": "Select a track to drive preview transport.",
        "Preview Waiting": "Preview transport is waiting for a valid track.",
    }

    guidance = _build_preview_guidance(
        preview_lifecycle_status=preview_lifecycle_status,
        preview_lifecycle_message=preview_lifecycle_message,
        preview_remount_pending=preview_remount_pending,
        background_path=background_path,
        preview_track_path=preview_track_path,
        pipeline_inputs=pipeline_inputs,
        gpu_preview_available=gpu_preview_available,
    )

    if saving:
        save_status = DiagnosticsBadge("Save In Flight", "running")
    elif workspace_dirty:
        save_status = DiagnosticsBadge("Local Draft Pending", "warning")
    else:
        save_status = DiagnosticsBadge("Template Synced", "ready")

    export = workspace.export if workspace else None
    if export and export.running:
        export_status = DiagnosticsBadge("Export Running", "running")
    elif pipeline_inputs and pipeline_inputs.ready:
        export_status = DiagnosticsBadge("Export Ready", "ready")
    elif pipeline_inputs and pipeline_inputs.run_dir:
        export_status = DiagnosticsBadge("Missing Export Inputs", "warning")
    else:
        export_status = DiagnosticsBadge("No Export Run", "neutral")

    if pipeline_inputs and pipeline_inputs.ready:
        pipeline_status = DiagnosticsBadge("Branch Inputs Ready", "ready")
    elif pipeline_inputs and pipeline_inputs.run_dir:
        pipeline_status = DiagnosticsBadge("Branch Inputs Missing", "warning")
    else:
        pipeline_status = DiagnosticsBadge("No Pipeline Inputs", "neutral")

    dirty_domains = (
        DiagnosticsDomainItem("Template", workspace_dirty),
        DiagnosticsDomainItem("Spectrum", bool(draft_dirty_map.get("spectrum"))),
        DiagnosticsDomainItem("Background", bool(draft_dirty_map.get("background"))),
        DiagnosticsDomainItem("Logo", bool(draft_dirty_map.get("logo"))),
        DiagnosticsDomainItem("Particles", bool(draft_dirty_map.get("particles"))),
        DiagnosticsDomainItem("Text", bool(draft_dirty_map.get("text"))),
    )

    perf = performance or {}
    frame_ms = float(perf.get("frameMs") or 0.0)
    fps = float(perf.get("fps") or 0.0)
    if frame_ms > 0:
        performance_label = f"{frame_ms:.1f} ms · {fps:.0f} fps · gate {export_gate_active}/{export_gate_limit}"
    else:
        performance_label = f"Idle · gate {export_gate_active}/{export_gate_limit}"

    return VideoWorkspaceDiagnosticsViewModel(
        preview_status_label=preview_status.label,
        preview_status_message=preview_messages.get(preview_status.label, preview_status.label),
        preview_status_tone=preview_status.tone,
        preview_guidance_title=guidance.title,
        preview_guidance_detail=guidance.detail,
        preview_guidance_items=guidance.items,
        preview_guidance_tone=guidance.tone,
        preview_needs_attention=guidance.visible,
        save_status_label=save_status.label,
        save_status_tone=save_status.tone,
        export_status_label=export_status.label,
        export_status_tone=export_status.tone,
        pipeline_status_label=pipeline_status.label,
        pipeline_status_tone=pipeline_status.tone,
        template_id=str(workspace.template_id if workspace else ""),
        branch_label=branch_label,
        background_label=_format_path(background_path, "No background attached"),
        track_label=_format_path(preview_track_path, "No preview track attached"),
        performance_label=performance_label,
        dirty_domains=dirty_domains,
        can_reset_local_draft=workspace_dirty,
    )


def build_video_workspace_diagnostics_payload(
    *,
    workspace: VideoWorkspaceState | None,
    template_name_draft: str,
    active_domain_tab: str,
    workspace_dirty: bool,
    draft_dirty_map: dict[str, bool],
    playback: VideoPlaybackState | None,
    preview_track_path: str,
    pipeline_branch: str,
    pipeline_inputs: ResolvedVideoPipelineInputs | None,
    preview_runtime_nonce: int,
    preview_lifecycle_status: str,
    preview_lifecycle_message: str,
    performance: dict[str, Any] | None,
    export_gate_active: int,
    export_gate_limit: int,
    diagnostics: VideoWorkspaceDiagnosticsViewModel,
) -> dict[str, Any]:
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "videoWorkspace": {
            "activeTab": active_domain_tab,
            "branch": pipeline_branch,
            "templateId": diagnostics.template_id,
            "templateName": template_name_draft.strip(),
            "previewRuntimeNonce": preview_runtime_nonce,
            "previewSource": workspace.ui.source if workspace else "python-local",
            "preview": {
                "status": diagnostics.preview_status_label,
                "message": diagnostics.preview_status_message,
                "lifecycleStatus": preview_lifecycle_status,
                "playback": (playback or VideoPlaybackState()).model_dump(by_alias=True),
                "trackPath": preview_track_path or None,
                "backgroundPath": workspace.background_path if workspace else None,
                "logoPath": workspace.logo_path if workspace else None,
                "aspectRatio": workspace.preview_aspect_ratio.model_dump(by_alias=True) if workspace else None,
                "performance": performance or {},
            },
            "save": {
                "status": diagnostics.save_status_label,
                "workspaceDirty": workspace_dirty,
                "draftDirtyState": draft_dirty_map,
            },
            "export": {
                "status": diagnostics.export_status_label,
                "running": bool(workspace.export.running if workspace else False),
                "currentStatus": workspace.export.current_status if workspace else "",
                "branch": workspace.export.branch if workspace else None,
                "lastOutputPath": workspace.export.last_output_path if workspace else None,
                "lastMergedOutputPath": workspace.export.last_merged_output_path if workspace else None,
                "gate": {"active": export_gate_active, "limit": export_gate_limit},
            },
            "pipeline": {
                "status": diagnostics.pipeline_status_label,
                "resolvedInputs": {
                    "branch": pipeline_inputs.branch if pipeline_inputs else pipeline_branch,
                    "ready": pipeline_inputs.ready if pipeline_inputs else False,
                    "runDir": pipeline_inputs.run_dir if pipeline_inputs else None,
                    "backgroundPath": pipeline_inputs.background_path if pipeline_inputs else None,
                },
            },
        },
    }


def serialize_diagnostics_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)
