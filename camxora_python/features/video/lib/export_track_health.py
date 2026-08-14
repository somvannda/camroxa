"""Classify per-track MP3 → MP4 health so repair export can skip good files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from features.video.lib.export_output_validity import export_matches_batch_specs, is_usable_export_output
from features.video.lib.render_scene_request import (
    MIN_VALID_EXPORT_BYTES,
    build_pipeline_export_output_path,
    is_valid_export_output,
)

TrackExportStatus = Literal[
    "ok",
    "missing_mp3",
    "missing_mp4",
    "tiny",
    "corrupt",
    "truncated",
    "spec_mismatch",
]

_NEEDS_EXPORT = frozenset({"missing_mp4", "tiny", "corrupt", "truncated", "spec_mismatch"})


@dataclass(frozen=True, slots=True)
class TrackExportHealth:
    mp3_path: str
    mp4_path: str
    status: TrackExportStatus
    detail: str = ""

    @property
    def needs_export(self) -> bool:
        return self.status in _NEEDS_EXPORT

    @property
    def needs_mp3(self) -> bool:
        return self.status == "missing_mp3"


def _mp3_sort_key(name: str) -> tuple[int, int, str] | tuple[int, str]:
    match = re.match(r"\s*(\d+)", name)
    if match:
        return (0, int(match.group(1)), name.lower())
    return (1, name.lower())


def list_run_mp3_paths(run_dir: str) -> list[str]:
    root = Path(str(run_dir or "").strip())
    try:
        if not root.is_dir():
            return []
        items = [
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() == ".mp3"
        ]
    except OSError:
        return []
    items.sort(key=lambda path: _mp3_sort_key(path.name))
    return [str(path) for path in items]


def inspect_run_export_health(
    run_dir: str,
    branch: str = "long",
    *,
    ffmpeg_path: str = "",
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_fps: int | float | None = None,
    mp3_paths: list[str] | None = None,
) -> list[TrackExportHealth]:
    """One row per MP3: missing, tiny, corrupt, spec mismatch, or ok."""
    normalized_branch = "reel" if str(branch or "").strip().lower() == "reel" else "long"
    sources = [str(path).strip() for path in (mp3_paths or list_run_mp3_paths(run_dir)) if str(path).strip()]
    results: list[TrackExportHealth] = []
    for mp3_path in sources:
        mp4_path = build_pipeline_export_output_path(
            mp3_path=mp3_path,
            output_dir=str(run_dir or "").strip(),
            branch=normalized_branch,
        )
        results.append(
            _classify_track(
                mp3_path=mp3_path,
                mp4_path=mp4_path,
                ffmpeg_path=ffmpeg_path,
                expected_width=expected_width,
                expected_height=expected_height,
                expected_fps=expected_fps,
            )
        )
    return results


def tracks_needing_export(health: list[TrackExportHealth]) -> list[str]:
    """MP3 paths that can be re-exported (source audio is present)."""
    return [item.mp3_path for item in health if item.needs_export]


def tracks_missing_mp3(health: list[TrackExportHealth]) -> list[str]:
    return [item.mp3_path for item in health if item.needs_mp3]


def summarize_export_health(health: list[TrackExportHealth]) -> str:
    needing = tracks_needing_export(health)
    missing_audio = tracks_missing_mp3(health)
    ok_count = sum(1 for item in health if item.status == "ok")
    parts = [f"{ok_count} usable MP4(s)"]
    if needing:
        parts.append(f"{len(needing)} need re-export")
    if missing_audio:
        parts.append(f"{len(missing_audio)} missing MP3(s)")
    return ", ".join(parts)


def select_export_mp3_paths(
    available: list[str],
    requested: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Keep album order; if requested, only those files that still exist in the run."""
    ordered = [str(path).strip() for path in available if str(path).strip()]
    if not requested:
        return ordered
    wanted_keys: set[str] = set()
    for raw in requested:
        text = str(raw or "").strip()
        if not text:
            continue
        path = Path(text)
        wanted_keys.add(str(path))
        wanted_keys.add(str(path).replace("\\", "/"))
        wanted_keys.add(path.name.lower())
    selected: list[str] = []
    for path in ordered:
        candidate = Path(path)
        keys = {str(candidate), str(candidate).replace("\\", "/"), candidate.name.lower()}
        if keys & wanted_keys:
            selected.append(path)
    return selected


def unlink_track_export(run_dir: str, mp3_path: str, branch: str = "long") -> str:
    """Delete one track's MP4 so a targeted regenerate cannot skip the existing file."""
    output_path = build_pipeline_export_output_path(
        mp3_path=mp3_path,
        output_dir=str(run_dir or "").strip(),
        branch="reel" if str(branch or "").strip().lower() == "reel" else "long",
    )
    try:
        Path(output_path).unlink(missing_ok=True)
    except OSError:
        pass
    return output_path


def manual_pipeline_start_kwargs(
    action: str,
    mp3_paths: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Flags for PipelineAutomationService.start() from a Progress menu action."""
    paths = [str(path).strip() for path in (mp3_paths or []) if str(path).strip()]
    normalized = str(action or "").strip()
    if normalized == "repair_export":
        return {
            "force_regenerate": False,
            "repair_unhealthy": True,
            "force_selected": False,
            "mp3_paths": paths or None,
        }
    if normalized == "force_export":
        return {
            "force_regenerate": True,
            "repair_unhealthy": False,
            "force_selected": bool(paths),
            "mp3_paths": paths or None,
        }
    return {
        "force_regenerate": False,
        "repair_unhealthy": False,
        "force_selected": False,
        "mp3_paths": paths or None,
    }


def decide_merge_prep(
    health: list[TrackExportHealth],
    *,
    skip_repair: bool = False,
) -> Literal["repair", "merge", "missing_audio", "no_mp4"]:
    """Whether Start Merging should re-export broken tracks first."""
    needing = tracks_needing_export(health)
    if not skip_repair and needing:
        return "repair"
    missing_audio = tracks_missing_mp3(health)
    ok_count = sum(1 for item in health if item.status == "ok")
    if missing_audio and not needing and ok_count == 0:
        return "missing_audio"
    if ok_count > 0:
        return "merge"
    return "no_mp4"


def _classify_track(
    *,
    mp3_path: str,
    mp4_path: str,
    ffmpeg_path: str,
    expected_width: int | None,
    expected_height: int | None,
    expected_fps: int | float | None,
) -> TrackExportHealth:
    mp3 = Path(mp3_path)
    try:
        mp3_ok = mp3.is_file()
    except OSError:
        mp3_ok = False
    if not mp3_ok:
        return TrackExportHealth(mp3_path, mp4_path, "missing_mp3", "MP3 is missing — download it first.")

    mp4 = Path(mp4_path)
    try:
        exists = mp4.is_file()
        size = mp4.stat().st_size if exists else 0
    except OSError:
        exists = False
        size = 0
    if not exists:
        return TrackExportHealth(mp3_path, mp4_path, "missing_mp4", "MP4 has not been exported yet.")
    if size < MIN_VALID_EXPORT_BYTES:
        return TrackExportHealth(
            mp3_path,
            mp4_path,
            "tiny",
            f"MP4 is too small ({size} bytes) — likely a stub or failed encode.",
        )

    if not is_usable_export_output(
        mp4_path,
        ffmpeg_path=ffmpeg_path,
        audio_path=mp3_path,
        require_media=True,
    ):
        if is_valid_export_output(mp4_path):
            return TrackExportHealth(
                mp3_path,
                mp4_path,
                "truncated",
                "MP4 is incomplete (duration/video stream does not match the audio).",
            )
        return TrackExportHealth(mp3_path, mp4_path, "corrupt", "MP4 is not a usable video file.")

    if expected_width and expected_height:
        if not export_matches_batch_specs(
            mp4_path,
            width=int(expected_width),
            height=int(expected_height),
            fps=float(expected_fps or 0),
            ffmpeg_path=ffmpeg_path,
            audio_path=mp3_path,
        ):
            return TrackExportHealth(
                mp3_path,
                mp4_path,
                "spec_mismatch",
                "MP4 does not match this batch resolution/FPS/audio layout.",
            )
    return TrackExportHealth(mp3_path, mp4_path, "ok")
