"""Desktop video runtime inspection — port of videoRuntimeInspection.ts."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.desktop import VideoWorkspaceState
from shared.models.platform import ProgressRow
from shared.services.file_service import DirectoryEntry, list_directory_entries


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


def _is_terminal_stage(stage: str) -> bool:
    normalized = str(stage or "").strip().lower()
    return normalized in {"youtube", "done", "error"}


def _stage_rank(stage: str) -> int:
    normalized = str(stage or "").strip().lower()
    ranks = {
        "music": 1,
        "image": 2,
        "converter": 3,
        "merger": 4,
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
    normalized_run_dir = _normalize_path(row.meta.run_dir)
    export = workspace.export if workspace else None
    active_run_dir = _normalize_path((export.output_dir if export else None) or "")
    is_active_run = bool(export and export.running and normalized_run_dir and normalized_run_dir == active_run_dir)
    active_branch = "reel" if export and export.branch == "reel" else "long"
    merge_running = bool(is_active_run and export and export.merge_running)
    export_running = bool(is_active_run and export and export.running and not export.merge_running)

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
    if expected < 2 and (long_count > 0 or reel_count > 0 or export_running or merge_running):
        long_merge_ratio = 1
        reel_merge_ratio = 1
    elif merge_running:
        if active_branch == "reel":
            reel_merge_ratio = 0.5
        else:
            long_merge_ratio = 0.5

    converter_percent = _clamp_percent(((long_ratio + reel_ratio) / 2) * 100)
    merge_percent = _clamp_percent(((long_merge_ratio + reel_merge_ratio) / 2) * 100)

    converter = row.converter
    if export_running and export:
        converter = export.current_status.strip() or (
            f"Converting {'reel' if active_branch == 'reel' else 'long'} videos…"
        )
    elif long_count > 0 or reel_count > 0:
        converter = (
            f"Long {min(long_count, expected)}/{expected} · "
            f"Reel {min(reel_count, expected)}/{expected}"
        )

    merge = row.merge
    if merge_running and export:
        merge = export.current_status.strip() or (
            f"Merging {'reel' if active_branch == 'reel' else 'long'} outputs…"
        )
    elif merged_long_count > 0 or merged_reel_count > 0:
        long_label = "Long merged" if merged_long_count > 0 else ("Long single" if expected < 2 else "Long pending")
        reel_label = "Reel merged" if merged_reel_count > 0 else ("Reel single" if expected < 2 else "Reel pending")
        merge = f"{long_label} · {reel_label}"
    elif expected < 2 and (long_count > 0 or reel_count > 0):
        merge = "Not required for a single-track run"
    elif long_count > 0 or reel_count > 0:
        merge = "Ready for merge once enough branch outputs exist"

    runtime_stage = row.stage
    runtime_status = row.status
    runtime_notes = row.notes

    if merge_running:
        runtime_stage = "Merger"
        runtime_status = "Merging"
        runtime_notes = (
            export.current_status.strip() if export and export.current_status.strip() else
            "Desktop merge is running for this batch/channel run."
        )
    elif export_running:
        runtime_stage = "Converter"
        runtime_status = "Converting"
        runtime_notes = (
            export.current_status.strip() if export and export.current_status.strip() else
            "Desktop video export is running for this batch/channel run."
        )
    elif merged_long_count > 0 or merged_reel_count > 0:
        runtime_stage = "Merger"
        merge_complete = (
            (merged_long_count > 0 or long_count > 0)
            if expected < 2
            else (merged_long_count > 0 and merged_reel_count > 0)
        )
        runtime_status = "Completed" if merge_complete else "Partial"
        runtime_notes = (
            "Merged outputs were detected locally in the run directory."
            if merge_complete
            else "Only part of the merge branches are ready locally; the other branch is still pending."
        )
    elif long_count > 0 or reel_count > 0:
        runtime_stage = "Converter"
        convert_complete = long_count >= expected and reel_count >= expected
        runtime_status = "Completed" if convert_complete else "Partial"
        runtime_notes = (
            "Exported MP4 outputs were detected locally in the run directory."
            if convert_complete
            else "Long and reel exports are only partially present in the run directory."
        )

    if not _should_override_stage(row.stage, runtime_stage):
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
