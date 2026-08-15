"""Auto-video candidate selection — port of desktopVideoAutomation.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from features.video.lib.pipeline_inputs import (
    ResolvedVideoPipelineInputs,
    VideoPipelineBranch,
    build_video_pipeline_run_key,
    local_audio_downloads_ready,
    resolve_local_video_pipeline_inputs,
)
from features.video.services.video_local_store import VideoLocalStore
from shared.lib.music_settings import read_boolean_setting
from shared.lib.video_runtime_inspection import ProgressRuntimePresentation, VideoRunInspection
from shared.models.auth import ProfileResponse
from shared.models.desktop import VideoWorkspaceState
from shared.models.platform import ProgressRow


@dataclass(frozen=True, slots=True)
class AutoVideoCandidate:
    key: str
    branch: VideoPipelineBranch
    batch_id: str
    role: str
    run_dir: str
    background_path: str
    template_id: str
    output_resolution: str | None
    profile_id: str | None = None


def _is_terminal_stage(stage: str) -> bool:
    normalized = str(stage or "").strip().lower()
    return normalized in {"youtube", "done", "completed", "error"}


def _has_expected_outputs(paths: tuple[str, ...] | list[str] | None, expected: int) -> bool:
    return len(paths or ()) >= max(1, expected)


def _workspace_has_template(workspace: VideoWorkspaceState | None, template_id: str) -> bool:
    normalized = str(template_id or "").strip()
    if not normalized:
        return False
    if workspace is not None and any(
        str(item.id or "").strip() == normalized for item in workspace.templates
    ):
        return True
    templates = VideoLocalStore().read_templates()
    return any(str(item.get("id") or "").strip() == normalized for item in templates)


def _branch_is_ready(
    row: ProgressRow,
    profile: ProfileResponse,
    branch: VideoPipelineBranch,
    *,
    workspace: VideoWorkspaceState | None,
) -> tuple[ResolvedVideoPipelineInputs | None, str | None]:
    inputs = resolve_local_video_pipeline_inputs(row, branch, profile)
    template_id = str(inputs.recommended_template_id or "").strip()
    run_dir = str(inputs.run_dir or "").strip()
    background_path = str(inputs.background_path or "").strip()
    if not inputs.ready:
        return None, "local image assets are missing"
    if not run_dir:
        return None, "run directory is missing"
    if not background_path:
        return None, "branch background image is missing"
    if not template_id:
        return None, "channel profile has no template assigned"
    if not _workspace_has_template(workspace, template_id):
        return None, f"template {template_id} is not in the local video catalog"
    return inputs, None


def select_next_auto_video_candidate(
    *,
    rows: list[ProgressRow],
    profiles: list[ProfileResponse],
    settings: dict[str, Any] | None,
    inspections: dict[str, VideoRunInspection],
    runtime_by_key: dict[str, ProgressRuntimePresentation],
    workspace: VideoWorkspaceState | None,
    skip_keys: set[str] | frozenset[str] | None = None,
) -> AutoVideoCandidate | None:
    if not read_boolean_setting(settings, "autoVideoAfterSuno", False):
        return None
    if workspace is not None and (workspace.export.running or workspace.export.merge_running):
        return None

    profiles_by_id = {profile.id: profile for profile in profiles}
    auto_reel_enabled = read_boolean_setting(settings, "autoReelAfterVideo", False)
    skipped = {str(key).strip() for key in (skip_keys or ()) if str(key).strip()}

    for row in rows:
        key = build_video_pipeline_run_key(row)
        if key in skipped:
            continue
        runtime = runtime_by_key.get(key)
        effective_stage = runtime.stage if runtime is not None else row.stage
        if _is_terminal_stage(effective_stage):
            continue

        profile = profiles_by_id.get(row.meta.profile_id)
        if profile is None:
            continue

        expected = max(1, int(row.meta.expected or 0))
        if not local_audio_downloads_ready(row):
            continue

        inspection = inspections.get(key)
        long_inputs, _long_reason = _branch_is_ready(row, profile, "long", workspace=workspace)
        reel_inputs, _reel_reason = _branch_is_ready(row, profile, "reel", workspace=workspace)
        long_outputs_ready = _has_expected_outputs(
            inspection.long_output_paths if inspection else (),
            expected,
        )
        reel_outputs_ready = _has_expected_outputs(
            inspection.reel_output_paths if inspection else (),
            expected,
        )

        if long_inputs is not None and not long_outputs_ready:
            return AutoVideoCandidate(
                key=key,
                branch="long",
                batch_id=row.meta.batch_id,
                role=row.meta.role,
                run_dir=str(long_inputs.run_dir or ""),
                background_path=str(long_inputs.background_path or ""),
                template_id=str(long_inputs.recommended_template_id or ""),
                output_resolution=profile.output_resolution,
                profile_id=str(row.meta.profile_id or "") or None,
            )

        if (
            auto_reel_enabled
            and reel_inputs is not None
            and long_outputs_ready
            and not reel_outputs_ready
        ):
            return AutoVideoCandidate(
                key=key,
                branch="reel",
                batch_id=row.meta.batch_id,
                role=row.meta.role,
                run_dir=str(reel_inputs.run_dir or ""),
                background_path=str(reel_inputs.background_path or ""),
                template_id=str(reel_inputs.recommended_template_id or ""),
                output_resolution=None,
                profile_id=str(row.meta.profile_id or "") or None,
            )

    return None


def build_auto_video_candidate_from_row(
    row: ProgressRow,
    profile: ProfileResponse,
    branch: VideoPipelineBranch,
    *,
    workspace: VideoWorkspaceState | None = None,
) -> AutoVideoCandidate | None:
    candidate, _reason = build_auto_video_candidate_from_row_with_reason(
        row,
        profile,
        branch,
        workspace=workspace,
    )
    return candidate


def build_auto_video_candidate_from_row_with_reason(
    row: ProgressRow,
    profile: ProfileResponse,
    branch: VideoPipelineBranch,
    *,
    workspace: VideoWorkspaceState | None = None,
) -> tuple[AutoVideoCandidate | None, str | None]:
    """Build an export candidate; returns a human-readable reason when blocked."""
    inputs, reason = _branch_is_ready(row, profile, branch, workspace=workspace)
    if inputs is None:
        return None, reason or "local image assets are missing"
    template_id = str(inputs.recommended_template_id or "").strip()
    run_dir = str(inputs.run_dir or "").strip()
    background_path = str(inputs.background_path or "").strip()
    if not run_dir:
        return None, "run directory is missing"
    if not background_path:
        return None, (
            "branch background image is missing "
            "(expected background-16x9 / background-16x9-alt in the run folder)"
        )
    if not template_id:
        return None, "channel profile has no template assigned"
    return (
        AutoVideoCandidate(
            key=build_video_pipeline_run_key(row),
            branch=branch,
            batch_id=row.meta.batch_id,
            role=row.meta.role,
            run_dir=run_dir,
            background_path=background_path,
            template_id=template_id,
            output_resolution=profile.output_resolution if branch == "long" else None,
            profile_id=str(row.meta.profile_id or "") or None,
        ),
        None,
    )


def build_merge_candidate_from_row(
    row: ProgressRow,
    profile: ProfileResponse,
    branch: VideoPipelineBranch,
) -> tuple[AutoVideoCandidate | None, str | None]:
    """Build a merge-only candidate (MP4 concat). Does not require BG or catalog template.

    Progress Continue already treats merge as "valid exported MP4s in the run folder";
    the coordinator must not re-apply the export readiness gate.
    """
    run_dir = str(row.meta.run_dir or "").strip()
    if not run_dir:
        return None, "run directory is missing"
    from pathlib import Path

    if not Path(run_dir).is_dir():
        return None, f"run directory does not exist: {run_dir}"

    # Optional context for status UI; merge itself only needs run_dir + branch.
    inputs = resolve_local_video_pipeline_inputs(row, branch, profile)
    template_id = str(inputs.recommended_template_id or "").strip()
    background_path = str(inputs.background_path or "").strip()
    return (
        AutoVideoCandidate(
            key=build_video_pipeline_run_key(row),
            branch=branch,
            batch_id=row.meta.batch_id,
            role=row.meta.role,
            run_dir=run_dir,
            background_path=background_path,
            template_id=template_id,
            output_resolution=profile.output_resolution if branch == "long" else None,
            profile_id=str(row.meta.profile_id or "") or None,
        ),
        None,
    )
