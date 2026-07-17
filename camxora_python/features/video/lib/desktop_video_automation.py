"""Auto-video candidate selection — port of desktopVideoAutomation.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from features.video.lib.pipeline_inputs import (
    VideoPipelineBranch,
    build_video_pipeline_run_key,
    resolve_video_pipeline_inputs,
)
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


def _read_boolean_setting(settings: dict[str, Any] | None, key: str, fallback: bool = False) -> bool:
    if not isinstance(settings, dict):
        return fallback
    value = settings.get(key)
    return value if isinstance(value, bool) else fallback


def _is_terminal_stage(stage: str) -> bool:
    normalized = str(stage or "").strip().lower()
    return normalized in {"youtube", "done", "error"}


def _has_expected_outputs(paths: tuple[str, ...] | list[str] | None, expected: int) -> bool:
    return len(paths or ()) >= max(1, expected)


def _has_downloaded_audio_ready(row: ProgressRow) -> bool:
    meta = row.meta
    expected = max(1, int(meta.expected or 0))
    downloaded = max(0, int(meta.saved or 0))
    download_ready = max(0, int(meta.download_ready or 0))
    pending_download = max(0, int(meta.download_pending or 0))
    return downloaded >= expected and download_ready >= expected and pending_download <= 0


def _workspace_has_template(workspace: VideoWorkspaceState | None, template_id: str) -> bool:
    normalized = str(template_id or "").strip()
    if not normalized or workspace is None:
        return False
    return any(str(item.id or "").strip() == normalized for item in workspace.templates)


def select_next_auto_video_candidate(
    *,
    rows: list[ProgressRow],
    profiles: list[ProfileResponse],
    settings: dict[str, Any] | None,
    inspections: dict[str, VideoRunInspection],
    runtime_by_key: dict[str, ProgressRuntimePresentation],
    workspace: VideoWorkspaceState | None,
) -> AutoVideoCandidate | None:
    if not _read_boolean_setting(settings, "autoVideoAfterSuno", False):
        return None
    if workspace is not None and (workspace.export.running or workspace.export.merge_running):
        return None

    profiles_by_id = {profile.id: profile for profile in profiles}
    auto_reel_enabled = _read_boolean_setting(settings, "autoReelAfterVideo", False)

    for row in rows:
        key = build_video_pipeline_run_key(row)
        runtime = runtime_by_key.get(key)
        effective_stage = runtime.stage if runtime is not None else row.stage
        if _is_terminal_stage(effective_stage):
            continue

        profile = profiles_by_id.get(row.meta.profile_id)
        if profile is None:
            continue

        expected = max(1, int(row.meta.expected or 0))
        if not _has_downloaded_audio_ready(row):
            continue

        inspection = inspections.get(key)
        long_inputs = resolve_video_pipeline_inputs(row, "long", profile)
        reel_inputs = resolve_video_pipeline_inputs(row, "reel", profile)
        long_outputs_ready = _has_expected_outputs(
            inspection.long_output_paths if inspection else (),
            expected,
        )
        reel_outputs_ready = _has_expected_outputs(
            inspection.reel_output_paths if inspection else (),
            expected,
        )

        if (
            long_inputs.ready
            and long_inputs.run_dir
            and long_inputs.background_path
            and long_inputs.recommended_template_id
            and _workspace_has_template(workspace, long_inputs.recommended_template_id)
            and not long_outputs_ready
        ):
            return AutoVideoCandidate(
                key=key,
                branch="long",
                batch_id=row.meta.batch_id,
                role=row.meta.role,
                run_dir=long_inputs.run_dir,
                background_path=long_inputs.background_path,
                template_id=long_inputs.recommended_template_id,
                output_resolution=profile.output_resolution,
                profile_id=str(row.meta.profile_id or "") or None,
            )

        if (
            auto_reel_enabled
            and reel_inputs.ready
            and reel_inputs.run_dir
            and reel_inputs.background_path
            and reel_inputs.recommended_template_id
            and _workspace_has_template(workspace, reel_inputs.recommended_template_id)
            and long_outputs_ready
            and not reel_outputs_ready
        ):
            return AutoVideoCandidate(
                key=key,
                branch="reel",
                batch_id=row.meta.batch_id,
                role=row.meta.role,
                run_dir=reel_inputs.run_dir,
                background_path=reel_inputs.background_path,
                template_id=reel_inputs.recommended_template_id,
                output_resolution=None,
                profile_id=str(row.meta.profile_id or "") or None,
            )

    return None
