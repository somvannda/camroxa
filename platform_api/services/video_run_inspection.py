"""Inspect local run-directory MP4 outputs for progress presentation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VideoRunInspection:
    directory: str
    long_output_paths: tuple[str, ...]
    reel_output_paths: tuple[str, ...]
    merged_long_paths: tuple[str, ...]
    merged_reel_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VideoRunPresentation:
    converter: str
    merge: str
    stage: str | None = None
    status: str | None = None
    notes: str | None = None


def inspect_video_run_directory(run_dir: str) -> VideoRunInspection | None:
    directory = str(run_dir or "").strip()
    base = Path(directory).expanduser()
    if not directory or not base.is_dir():
        return None

    long_paths: list[str] = []
    reel_paths: list[str] = []
    merged_long_paths: list[str] = []
    merged_reel_paths: list[str] = []

    for path in sorted(base.iterdir()):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if not lower.endswith(".mp4"):
            continue
        resolved = str(path.resolve())
        if lower.startswith("merged_reel_"):
            merged_reel_paths.append(resolved)
        elif lower.startswith("merged_"):
            merged_long_paths.append(resolved)
        elif lower.endswith("_reel.mp4"):
            reel_paths.append(resolved)
        else:
            long_paths.append(resolved)

    return VideoRunInspection(
        directory=str(base.resolve()),
        long_output_paths=tuple(long_paths),
        reel_output_paths=tuple(reel_paths),
        merged_long_paths=tuple(merged_long_paths),
        merged_reel_paths=tuple(merged_reel_paths),
    )


def build_video_run_presentation(
    *,
    inspection: VideoRunInspection | None,
    expected: int,
    assets_ready: bool,
) -> VideoRunPresentation:
    expected_count = max(1, int(expected or 0))
    if inspection is None:
        if assets_ready:
            return VideoRunPresentation(
                converter="Assets ready · no exports yet",
                merge="Waiting for branch exports",
            )
        return VideoRunPresentation(
            converter="Waiting for image assets",
            merge="—",
        )

    long_count = len(inspection.long_output_paths)
    reel_count = len(inspection.reel_output_paths)
    merged_long_count = len(inspection.merged_long_paths)
    merged_reel_count = len(inspection.merged_reel_paths)

    if long_count > 0 or reel_count > 0:
        converter = (
            f"Long {min(long_count, expected_count)}/{expected_count} · "
            f"Reel {min(reel_count, expected_count)}/{expected_count}"
        )
    elif assets_ready:
        converter = "Assets ready · no exports yet"
    else:
        converter = "Waiting for image assets"

    if merged_long_count > 0 or merged_reel_count > 0:
        long_label = "Long merged" if merged_long_count > 0 else (
            "Long single" if expected_count < 2 else "Long pending"
        )
        reel_label = "Reel merged" if merged_reel_count > 0 else (
            "Reel single" if expected_count < 2 else "Reel pending"
        )
        merge = f"{long_label} · {reel_label}"
        return VideoRunPresentation(
            converter=converter,
            merge=merge,
            stage="Merger",
            status="Completed",
            notes="Merged outputs were detected locally in the run directory.",
        )

    if long_count > 0 or reel_count > 0:
        if expected_count < 2:
            merge = "Not required for a single-track run"
        else:
            merge = "Ready for merge once enough branch outputs exist"
        return VideoRunPresentation(
            converter=converter,
            merge=merge,
            stage="Converter",
            status="Completed",
            notes="Exported MP4 outputs were detected locally in the run directory.",
        )

    merge = "Waiting for branch exports" if assets_ready else "—"
    return VideoRunPresentation(converter=converter, merge=merge)
