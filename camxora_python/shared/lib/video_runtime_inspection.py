"""Desktop video runtime inspection — port of videoRuntimeInspection.ts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from shared.models.desktop import VideoWorkspaceState
from shared.models.platform import ProgressRow
from shared.services.file_service import DirectoryEntry, list_directory_entries

# Same floor as pipeline export (MIN_VALID_EXPORT_BYTES). Keep local so Progress
# listing does not import the video feature package.
_MIN_USABLE_EXPORT_BYTES = 50_000

# Standard pipeline status vocabulary (Progress + Workflow surfaces).
STATUS_NOT_STARTED = "Not started"
STATUS_PENDING = "Pending"
STATUS_IN_PROGRESS = "In Progress"
STATUS_COMPLETED = "Completed"

# Display stage labels aligned with Export / Merge column activities.
STAGE_EXPORT = "Export"
STAGE_MERGE = "Merge"


@dataclass(frozen=True, slots=True)
class VideoRunInspection:
    directory: str
    long_output_paths: tuple[str, ...]
    reel_output_paths: tuple[str, ...]
    merged_long_paths: tuple[str, ...]
    merged_reel_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProgressRuntimePresentation:
    converter: str
    merge: str
    stage: str
    status: str
    notes: str
    converter_percent: int
    merge_percent: int


def progress_runtime_key(batch_id: str, profile_id: str, role: str) -> str:
    return f"{batch_id}:{profile_id}:{role}"


def _clamp_percent(value: float) -> int:
    return max(0, min(100, round(value)))


def _normalize_path(value: str | None) -> str:
    return str(value or "").strip().rstrip("\\/").lower()


def _join_windows_path(directory: str, name: str) -> str:
    base = str(directory or "").strip().rstrip("\\/")
    return f"{base}\\{name}" if base else name


def _is_tiny_on_disk_export(directory: str, name: str) -> bool:
    """True only when the file exists locally and is smaller than a valid export."""
    from pathlib import Path

    try:
        path = Path(str(directory or "").strip()) / name
        if not path.is_file():
            return False
        return path.stat().st_size < _MIN_USABLE_EXPORT_BYTES
    except OSError:
        return False


def _normalize_stage_key(stage: str) -> str:
    normalized = str(stage or "").strip().lower()
    if normalized in {"converter", "export"}:
        return "export"
    if normalized in {"merger", "merge"}:
        return "merge"
    return normalized


def _is_terminal_stage(stage: str) -> bool:
    return _normalize_stage_key(stage) in {"youtube", "done", "completed", "error"}


def _stage_rank(stage: str) -> int:
    normalized = _normalize_stage_key(stage)
    ranks = {
        "music": 1,
        "image": 2,
        "export": 3,
        "merge": 4,
        "youtube": 5,
        "done": 6,
        "error": 7,
    }
    return ranks.get(normalized, 0)


def _should_override_stage(api_stage: str, runtime_stage: str) -> bool:
    if not runtime_stage:
        return False
    if _is_terminal_stage(api_stage):
        return False
    return _stage_rank(runtime_stage) >= _stage_rank(api_stage)


def _standardize_runtime_status(status: str) -> str:
    key = str(status or "").strip().lower()
    if key in {"completed", "done", "success"}:
        return STATUS_COMPLETED
    if key in {"partial", "converting", "merging", "rendering", "downloading", "uploading", "running", "processing"}:
        return STATUS_IN_PROGRESS
    if key in {"queued", "waiting", "preparing"}:
        return STATUS_PENDING
    if key in {"not started", "idle", "—", "-", ""}:
        return STATUS_NOT_STARTED
    if key == "failed":
        return "Failed"
    if key == "blocked":
        return "Blocked"
    return str(status or "").strip() or STATUS_PENDING


def run_includes_reel(
    row: ProgressRow,
    runtime: ProgressRuntimePresentation | None = None,
) -> bool:
    """True when reel is part of this run (9x16 assets or real reel branch progress)."""
    if row.meta.reel_ready:
        return True
    if row.meta.background_9x16_path or row.meta.thumbnail_9x16_path:
        return True

    converter = runtime.converter if runtime else row.converter
    merge = runtime.merge if runtime else row.merge
    combined = f"{converter}\n{merge}".lower()

    count_match = re.search(r"reel\s+(\d+)\s*/\s*(\d+)", combined)
    if count_match is not None and int(count_match.group(1)) > 0:
        return True
    if any(
        token in combined
        for token in (
            "reel merged",
            "reel single",
            "reel completed",
            "exporting reel",
            "merging reel",
        )
    ):
        return True
    return False


def _branch_merge_label(*, completed: bool, single_track: bool, branch: str) -> str:
    prefix = "Long" if branch == "long" else "Reel"
    if completed:
        return f"{prefix} completed"
    if single_track:
        return f"{prefix} single"
    return f"{prefix} pending"


def inspect_video_run_entries(directory: str, entries: list[DirectoryEntry]) -> VideoRunInspection:
    inspection = VideoRunInspection(
        directory=str(directory or "").strip(),
        long_output_paths=(),
        reel_output_paths=(),
        merged_long_paths=(),
        merged_reel_paths=(),
    )
    long_paths: list[str] = []
    reel_paths: list[str] = []
    merged_long_paths: list[str] = []
    merged_reel_paths: list[str] = []

    for entry in entries:
        if entry.is_directory:
            continue
        name = str(entry.name or "").strip()
        lower = name.lower()
        if not lower.endswith(".mp4"):
            continue
        if _is_tiny_on_disk_export(inspection.directory, name):
            continue
        full_path = _join_windows_path(inspection.directory, name)
        if lower.startswith("merged_reel_"):
            merged_reel_paths.append(full_path)
        elif lower.startswith("merged_"):
            merged_long_paths.append(full_path)
        elif lower.endswith("_reel.mp4"):
            reel_paths.append(full_path)
        else:
            long_paths.append(full_path)

    return VideoRunInspection(
        directory=inspection.directory,
        long_output_paths=tuple(sorted(long_paths)),
        reel_output_paths=tuple(sorted(reel_paths)),
        merged_long_paths=tuple(sorted(merged_long_paths)),
        merged_reel_paths=tuple(sorted(merged_reel_paths)),
    )


def resolve_progress_runtime_presentation(
    row: ProgressRow,
    inspection: VideoRunInspection | None,
    workspace: VideoWorkspaceState | None,
) -> ProgressRuntimePresentation:
    expected = max(1, int(row.meta.expected or 0))
    long_count = len(inspection.long_output_paths) if inspection else 0
    reel_count = len(inspection.reel_output_paths) if inspection else 0
    merged_long_count = len(inspection.merged_long_paths) if inspection else 0
    merged_reel_count = len(inspection.merged_reel_paths) if inspection else 0
    include_reel = run_includes_reel(row)
    normalized_run_dir = _normalize_path(row.meta.run_dir)
    export = workspace.export if workspace else None
    active_run_dir = _normalize_path((export.output_dir if export else None) or "")
    is_active_run = bool(export and export.running and normalized_run_dir and normalized_run_dir == active_run_dir)
    active_branch = "reel" if export and export.branch == "reel" else "long"
    merge_running = bool(is_active_run and export and export.merge_running)
    export_running = bool(is_active_run and export and export.running and not export.merge_running)
    has_local_video_evidence = bool(
        inspection
        and (
            long_count > 0
            or reel_count > 0
            or merged_long_count > 0
            or merged_reel_count > 0
        )
    )

    long_ratio = min(long_count / expected, 1) if expected > 0 else 0
    reel_ratio = min(reel_count / expected, 1) if expected > 0 else 0

    if export_running and export and (export.total_jobs or 0) > 0:
        running_ratio = min(
            (export.completed_jobs or 0) / max(export.total_jobs or 1, 1),
            1,
        )
        if active_branch == "reel":
            reel_ratio = max(reel_ratio, running_ratio)
        else:
            long_ratio = max(long_ratio, running_ratio)

    long_merge_ratio = 1 if merged_long_count > 0 else 0
    reel_merge_ratio = 1 if merged_reel_count > 0 else 0
    single_track = expected < 2
    if single_track and (long_count > 0 or reel_count > 0 or export_running or merge_running):
        long_merge_ratio = 1
        reel_merge_ratio = 1
    elif merge_running:
        if active_branch == "reel":
            reel_merge_ratio = 0.5
        else:
            long_merge_ratio = 0.5

    if include_reel:
        converter_percent = _clamp_percent(((long_ratio + reel_ratio) / 2) * 100)
        merge_percent = _clamp_percent(((long_merge_ratio + reel_merge_ratio) / 2) * 100)
    else:
        converter_percent = _clamp_percent(long_ratio * 100)
        merge_percent = _clamp_percent(long_merge_ratio * 100)

    converter = row.converter
    if export_running and export:
        converter = export.current_status.strip() or (
            f"Exporting {'reel' if active_branch == 'reel' else 'long'} videos…"
        )
    elif long_count > 0 or reel_count > 0:
        if include_reel:
            converter = (
                f"Long {min(long_count, expected)}/{expected} · "
                f"Reel {min(reel_count, expected)}/{expected}"
            )
        else:
            converter = f"Long {min(long_count, expected)}/{expected}"
    elif (row.meta.long_ready or row.meta.reel_ready) and "waiting for image assets" in str(converter).lower():
        converter = "Pending · no exports yet"

    merge = row.merge
    if merge_running and export:
        merge = export.current_status.strip() or (
            f"Merging {'reel' if active_branch == 'reel' else 'long'} outputs…"
        )
    elif merged_long_count > 0 or merged_reel_count > 0:
        long_label = _branch_merge_label(
            completed=merged_long_count > 0,
            single_track=single_track,
            branch="long",
        )
        if include_reel:
            reel_label = _branch_merge_label(
                completed=merged_reel_count > 0,
                single_track=single_track,
                branch="reel",
            )
            merge = f"{long_label} · {reel_label}"
        else:
            merge = long_label
    elif single_track and (long_count > 0 or reel_count > 0):
        merge = "Not required for a single-track run"
    elif long_count > 0 or reel_count > 0:
        merge = "Pending · waiting for branch exports"

    runtime_stage = row.stage
    runtime_status = row.status
    runtime_notes = row.notes

    export_complete = long_count >= expected and (reel_count >= expected if include_reel else True)
    merge_complete = (
        merged_long_count > 0
        if not include_reel
        else (
            (merged_long_count > 0 or long_count > 0)
            if single_track
            else (merged_long_count > 0 and merged_reel_count > 0)
        )
    )

    if merge_running:
        runtime_stage = STAGE_MERGE
        runtime_status = STATUS_IN_PROGRESS
        runtime_notes = (
            export.current_status.strip() if export and export.current_status.strip() else
            "Desktop merge is running for this batch/channel run."
        )
    elif merged_long_count > 0 or merged_reel_count > 0:
        runtime_stage = STAGE_MERGE
        runtime_status = STATUS_COMPLETED if merge_complete else STATUS_IN_PROGRESS
        runtime_notes = (
            "Merged outputs were detected locally in the run directory."
            if merge_complete
            else "Only part of the merge branches are ready locally; the other branch is still pending."
        )
    elif export_running:
        runtime_stage = STAGE_EXPORT
        runtime_status = STATUS_IN_PROGRESS
        runtime_notes = (
            export.current_status.strip() if export and export.current_status.strip() else
            "Desktop video export is running for this batch/channel run."
        )
    elif long_count > 0 or reel_count > 0:
        runtime_stage = STAGE_EXPORT
        runtime_status = STATUS_COMPLETED if export_complete else STATUS_IN_PROGRESS
        runtime_notes = (
            "Exported MP4 outputs were detected locally in the run directory."
            if export_complete
            else (
                "Long and reel exports are only partially present in the run directory."
                if include_reel
                else "Long exports are only partially present in the run directory."
            )
        )

    if has_local_video_evidence:
        runtime_status = _standardize_runtime_status(runtime_status)
    elif not _should_override_stage(row.stage, runtime_stage):
        runtime_stage = row.stage
        runtime_status = row.status
        runtime_notes = row.notes

    return ProgressRuntimePresentation(
        converter=converter,
        merge=merge,
        stage=runtime_stage,
        status=runtime_status,
        notes=runtime_notes,
        converter_percent=converter_percent,
        merge_percent=merge_percent,
    )


def build_runtime_presentation_map(
    rows: list[ProgressRow],
    workspace: VideoWorkspaceState | None,
) -> dict[str, ProgressRuntimePresentation]:
    inspections = build_video_run_inspection_map(rows)

    return {
        progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role): resolve_progress_runtime_presentation(
            row,
            inspections.get(progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)),
            workspace,
        )
        for row in rows
    }


def build_video_run_inspection_map(rows: list[ProgressRow]) -> dict[str, VideoRunInspection]:
    inspections: dict[str, VideoRunInspection] = {}
    for row in rows:
        key = progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
        directory = str(row.meta.run_dir or "").strip()
        if not directory:
            continue
        entries = list_directory_entries(directory)
        inspections[key] = inspect_video_run_entries(directory, entries)
    return inspections
