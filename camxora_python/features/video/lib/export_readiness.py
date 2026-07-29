"""Consolidated export readiness validation for Progress + automation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from features.video.lib.desktop_video_automation import _workspace_has_template
from features.video.lib.pipeline_inputs import resolve_local_video_pipeline_inputs
from features.video.services.video_local_store import VideoLocalStore
from shared.lib.channel_asset_paths import resolve_local_channel_asset_paths
from shared.lib.mp3_naming import mp3_channel_label, mp3_naming_hint
from shared.lib.progress_local_sync import local_mp3_files_ready
from shared.models.auth import ProfileResponse
from shared.models.desktop import VideoWorkspaceState
from shared.models.platform import ProgressRow


@dataclass(frozen=True, slots=True)
class VideoExportReadiness:
    ready: bool
    issues: tuple[str, ...]


def evaluate_video_export_readiness(
    row: ProgressRow | None,
    profile: ProfileResponse | None,
    *,
    branch: str = "long",
    workspace: VideoWorkspaceState | None = None,
    progress_load_error: str | None = None,
    auth_blocked: bool = False,
) -> VideoExportReadiness:
    issues: list[str] = []
    if progress_load_error:
        issues.append(
            f"/progress failed to load ({progress_load_error}). Refresh Progress before exporting."
        )
    if auth_blocked:
        issues.append("Sign in again — billing/auth is blocking video export.")

    if row is None:
        issues.append("Select a progress row to validate export readiness.")
        return VideoExportReadiness(ready=False, issues=tuple(issues))

    meta = row.meta
    normalized_branch = "reel" if str(branch or "").strip().lower() == "reel" else "long"
    run_dir = str(meta.run_dir or "").strip()
    if not run_dir:
        issues.append("Run folder path is missing (Open Run Folder from row menu).")
    else:
        run_path = Path(run_dir)
        if not run_path.is_dir():
            issues.append(f"Run folder does not exist: {run_dir}")
        else:
            assets = resolve_local_channel_asset_paths(run_dir, channel_role=meta.role)
            if normalized_branch == "long":
                bg_path = assets.get("background_16x9_path")
                bg_name = "background-16x9.png"
            else:
                bg_path = assets.get("background_9x16_path")
                bg_name = "background-9x16.png"
            # Thumbnail is for YouTube upload only — not required for video export.
            if not bg_path:
                issues.append(f"Missing {bg_name} in run folder.")

            expected = max(1, int(meta.expected or 0))
            if not local_mp3_files_ready(row):
                suffix_hint = mp3_naming_hint(meta.role)
                channel = mp3_channel_label(meta.role)
                issues.append(
                    f"Need {expected} {channel} MP3 file(s) named like `{suffix_hint}` in the run folder."
                )

    inputs = resolve_local_video_pipeline_inputs(row, normalized_branch, profile)
    template_id = str(inputs.recommended_template_id or "").strip()
    if profile is None:
        issues.append("Channel profile not found for this row.")
    elif not template_id:
        label = "Reel template" if normalized_branch == "reel" else "Long video template"
        issues.append(f"Assign a {label} on Settings → Profile for this channel.")
    elif not _workspace_has_template(workspace, template_id):
        issues.append(
            f"Template `{template_id}` is not in the local Video catalog (Video page → refresh templates)."
        )

    if not inputs.ready and run_dir:
        if not str(inputs.background_path or "").strip():
            issues.append(f"Local {normalized_branch} branch assets incomplete: background.")

    store = VideoLocalStore()
    if run_dir and local_mp3_files_ready(row) and not store.list_mp3_files(run_dir):
        issues.append("Run folder MP3 files exist but could not be listed for export.")

    return VideoExportReadiness(ready=len(issues) == 0, issues=tuple(issues))
