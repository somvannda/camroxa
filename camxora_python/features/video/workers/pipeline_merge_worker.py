"""Background worker for pipeline export auto-merge."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from features.video.lib.pipeline_merge import (
    MergeEncodeSettings,
    build_merged_output_path,
    collect_verified_merge_inputs,
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
    encode: MergeEncodeSettings | None = None


class VideoPipelineMergeWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, request: PipelineMergeRequest, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoPipelineMergeWorker")
        self._request = request
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        request = self._request
        branch = "reel" if request.branch == "reel" else "long"
        branch_label = "reel" if branch == "reel" else "long"

        def emit_progress(message: str, percent: int | None = None) -> None:
            payload: dict[str, object] = {"status": "merging", "message": message}
            if percent is not None:
                payload["progress"] = max(0, min(100, int(percent)))
            self.progressed.emit(payload)

        emit_progress(f"Merging {branch_label} video outputs…", 0)
        encode = request.encode
        branch_outputs = collect_verified_merge_inputs(
            list(request.mp4_paths) if request.mp4_paths else [],
            run_dir=request.run_dir,
            branch=branch,
            ffmpeg_path=request.ffmpeg_path,
            expected_width=int(encode.width) if encode else None,
            expected_height=int(encode.height) if encode else None,
            expected_fps=int(encode.fps) if encode else None,
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
                encode=request.encode,
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
