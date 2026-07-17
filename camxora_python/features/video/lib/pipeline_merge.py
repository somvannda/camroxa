"""Pipeline export merge helpers — port of camxora main process mergeVideoOutputs."""

from __future__ import annotations

import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from features.video.lib.render_scene_request import MIN_VALID_EXPORT_BYTES, is_valid_export_output
from features.video.services.export_job import find_ffmpeg_from_path_hint
from shared.lib.subprocess_utils import run_hidden

ProgressCallback = Callable[[str], None]


def safe_batch_suffix(batch_id: str) -> str:
    text = str(batch_id or "").strip()
    match = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-(\d+)-(\d+)$", text, re.IGNORECASE)
    if match:
        return f"{match.group(1)}_{match.group(2)}_{match.group(3)}"
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)
    return safe[-80:] if len(safe) > 80 else safe


def normalize_merge_role(role: str) -> str:
    normalized = str(role or "").strip().lower()
    return "SECONDARY" if normalized in {"alt", "secondary"} else "PRIMARY"


from shared.lib.music_settings import read_boolean_setting


def is_auto_merge_enabled_for_branch(settings: dict, branch: str) -> bool:
    if not read_boolean_setting(settings, "autoMergeAfterVideo", False):
        return False
    if branch == "reel":
        return read_boolean_setting(settings, "autoReelAfterVideo", False)
    return True


def build_merged_output_path(*, output_dir: str, batch_id: str, role: str, branch: str) -> str:
    suffix = safe_batch_suffix(batch_id) or "batch"
    normalized_role = normalize_merge_role(role)
    file_name = (
        f"MERGED_REEL_{normalized_role}_{suffix}.mp4"
        if branch == "reel"
        else f"MERGED_{normalized_role}_{suffix}.mp4"
    )
    return str(Path(output_dir) / file_name)


def list_branch_export_outputs(output_dir: str, branch: str) -> list[str]:
    root = Path(str(output_dir or "").strip())
    if not root.is_dir():
        return []
    results: list[str] = []
    try:
        for entry in root.iterdir():
            if not entry.is_file():
                continue
            lower = entry.name.lower()
            if not lower.endswith(".mp4") or lower.startswith("merged_"):
                continue
            if branch == "reel":
                if not lower.endswith("_reel.mp4"):
                    continue
            elif lower.endswith("_reel.mp4"):
                continue
            target = str(entry)
            if is_valid_export_output(target):
                results.append(target)
    except OSError:
        return []
    return sorted(results)


def find_ffprobe_from_path_hint(ffmpeg_path: str) -> str:
    from shared.lib.ffmpeg_paths import resolve_ffprobe_path

    resolved = resolve_ffprobe_path(ffmpeg_path)
    return resolved if Path(resolved).is_file() else ""


def _escape_ffconcat_path(target_path: str) -> str:
    return str(target_path or "").replace("'", "'\\''")


def _is_file_stable(target_path: str) -> bool:
    path = Path(target_path)
    try:
        previous = path.stat()
        if not previous.is_file():
            return False
        with path.open("rb") as handle:
            handle.read(1)
    except OSError:
        return False

    for _ in range(10):
        time.sleep(0.4)
        try:
            current = path.stat()
            if previous.st_size == current.st_size and previous.st_mtime_ns == current.st_mtime_ns:
                return True
            previous = current
        except OSError:
            return False
    return False


def _probe_video_duration(target_path: str, ffprobe_path: str) -> float:
    if not ffprobe_path or not Path(ffprobe_path).is_file():
        return 0.0
    try:
        completed = run_hidden(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                target_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return 0.0
    try:
        parsed = float(str(completed.stdout or "").strip() or "0")
    except ValueError:
        return 0.0
    return max(0.0, parsed) if parsed == parsed else 0.0


def _write_merge_order_log(target_path: str, original_order: list[str], shuffled_order: list[str]) -> None:
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        order_path = Path(target_path).parent / f"MERGE_ORDER_{stamp}.txt"
        order_path.write_text(
            "ORIGINAL:\n"
            + "\n".join(original_order)
            + "\n\nSHUFFLED:\n"
            + "\n".join(shuffled_order)
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _prepare_merge_inputs(valid_paths: list[str], temp_dir: Path) -> list[str]:
    prepared: list[str] = []
    for index, src_path in enumerate(valid_paths, start=1):
        target_path = temp_dir / f"{index:04d}.mp4"
        try:
            target_path.hardlink_to(src_path)
        except OSError:
            import shutil

            shutil.copyfile(src_path, target_path)
        prepared.append(str(target_path).replace("\\", "/"))
    return prepared


def merge_video_outputs(
    *,
    ffmpeg_path: str,
    mp4_paths: list[str],
    target_path: str,
    on_progress: ProgressCallback | None = None,
    cancel_check: Callable[[], bool] | None = None,
    shuffle: bool = True,
) -> str | None:
    requested = [str(path).strip() for path in mp4_paths if str(path).strip()]
    if len(requested) < 2:
        return None
    if is_valid_export_output(target_path):
        return target_path

    emit = on_progress or (lambda _message: None)
    cancel = cancel_check or (lambda: False)
    resolved_ffmpeg = find_ffmpeg_from_path_hint(ffmpeg_path)
    ffprobe_path = find_ffprobe_from_path_hint(resolved_ffmpeg)

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    valid_paths: list[str] = []
    skipped_paths: list[str] = []
    for file_path in requested:
        if cancel():
            raise RuntimeError("Video export stopped.")
        try:
            stat = Path(file_path).stat()
            if not stat.is_file() or stat.st_size < MIN_VALID_EXPORT_BYTES:
                skipped_paths.append(file_path)
                continue
            if not _is_file_stable(file_path):
                skipped_paths.append(file_path)
                continue
            if ffprobe_path:
                duration = _probe_video_duration(file_path, ffprobe_path)
                if duration <= 0.05:
                    skipped_paths.append(file_path)
                    continue
            valid_paths.append(file_path)
        except OSError:
            skipped_paths.append(file_path)

    if skipped_paths:
        shown = ", ".join(Path(path).name for path in skipped_paths[:8])
        extra = f" (+{len(skipped_paths) - 8} more)" if len(skipped_paths) > 8 else ""
        emit(f"Skipping {len(skipped_paths)} incomplete MP4 file(s): {shown}{extra}")

    if len(valid_paths) < 2:
        return None

    original_order = [Path(path).name for path in valid_paths]
    shuffled = list(valid_paths)
    if shuffle:
        random.shuffle(shuffled)
    _write_merge_order_log(target_path, original_order, [Path(path).name for path in shuffled])

    temp_dir = Path(target.parent) / f"camxora-merge-{int(time.time() * 1000)}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        prepared_inputs = _prepare_merge_inputs(shuffled, temp_dir)
        concat_file_path = temp_dir / "merge-list.txt"
        concat_contents = "\n".join(
            ["ffconcat version 1.0", *[f"file '{_escape_ffconcat_path(path)}'" for path in prepared_inputs]]
        )
        concat_file_path.write_text(f"{concat_contents}\n", encoding="utf-8")

        def run_ffmpeg(args: list[str]) -> None:
            if cancel():
                raise RuntimeError("Video export stopped.")
            emit("Preparing FFmpeg merge…")
            completed = run_hidden(
                [resolved_ffmpeg, *args],
                capture_output=True,
                text=True,
                check=False,
            )
            if cancel():
                raise RuntimeError("Video export stopped.")
            if completed.returncode != 0:
                raise RuntimeError((completed.stderr or "").strip() or f"Video merge exited with code {completed.returncode}")

        run_ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", str(concat_file_path), "-c", "copy", target_path])
        if is_valid_export_output(target_path):
            return target_path

        emit("FFmpeg copy merge failed, retrying with re-encode…")
        run_ffmpeg(
            [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file_path),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                target_path,
            ]
        )
        if not is_valid_export_output(target_path):
            raise RuntimeError("Merged output is missing or invalid.")
        return target_path
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
