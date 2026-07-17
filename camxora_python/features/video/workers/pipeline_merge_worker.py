"""Background worker for pipeline export auto-merge."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from features.video.lib.pipeline_merge import (
    build_merged_output_path,
    list_branch_export_outputs,
    merge_video_outputs,
)


@dataclass(frozen=True)
class PipelineMergeRequest:
    run_dir: str
    branch: str
    batch_id: str
    role: str
    ffmpeg_path: str
    completed: int
    total: int
    # Manual batches pass explicit outputs in track order and skip shuffling.
    mp4_paths: tuple[str, ...] = ()
    shuffle: bool = True


class VideoPipelineMergeWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, request: PipelineMergeRequest, parent=None) -> None:
        super().__init__(parent)
        self._request = request
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        request = self._request
        branch = "reel" if request.branch == "reel" else "long"
        branch_label = "reel" if branch == "reel" else "long"

        def emit_progress(message: str) -> None:
            self.progressed.emit({"status": "merging", "message": message})

        emit_progress(f"Merging {branch_label} video outputs…")
        branch_outputs = (
            list(request.mp4_paths)
            if request.mp4_paths
            else list_branch_export_outputs(request.run_dir, branch)
        )
        merged_target_path = build_merged_output_path(
            output_dir=request.run_dir,
            batch_id=request.batch_id,
            role=request.role,
            branch=branch,
        )
        try:
            merged_path = merge_video_outputs(
                ffmpeg_path=request.ffmpeg_path,
                mp4_paths=branch_outputs,
                target_path=merged_target_path,
                on_progress=emit_progress,
                cancel_check=lambda: self._cancel_requested,
                shuffle=request.shuffle,
            )
        except Exception as exc:
            if self._cancel_requested:
                self.failed.emit("Video export stopped.")
                return
            self.failed.emit(str(exc) or "Video merge failed.")
            return

        if self._cancel_requested:
            self.failed.emit("Video export stopped.")
            return

        completed = int(request.completed)
        total = int(request.total)
        if merged_path:
            self.succeeded.emit(
                {
                    "mergedOutputPath": merged_path,
                    "completed": completed,
                    "total": total,
                    "branch": branch,
                    "message": (
                        f"Export and merge complete · {completed}/{total} {branch_label} video(s)."
                    ),
                }
            )
            return

        self.succeeded.emit(
            {
                "mergedOutputPath": None,
                "completed": completed,
                "total": total,
                "branch": branch,
                "message": (
                    f"Export complete · {completed}/{total} {branch_label} video(s). "
                    "Merge skipped because at least two valid MP4 files are required."
                ),
            }
        )
