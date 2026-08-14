"""Pipeline export merge helpers — port of camxora main process mergeVideoOutputs."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from features.video.lib.export_output_validity import (
    assert_concat_copy_compatible,
    export_media_looks_complete,
    is_usable_export_output,
)
from features.video.lib.render_scene_request import (
    MIN_VALID_EXPORT_BYTES,
    REEL_EXPORT_RESOLUTION,
    is_valid_export_output,
    normalize_export_fps,
    parse_render_resolution,
)
from features.video.services.export_job import find_ffmpeg_from_path_hint
from shared.lib.export_codec import normalize_export_speed_mode
from shared.lib.export_tiers import resolve_export_tier_settings
from shared.lib.music_settings import read_boolean_setting
from shared.lib.subprocess_utils import popen_hidden, run_hidden

ProgressCallback = Callable[[str, int | None], None]


@dataclass(frozen=True, slots=True)
class MergeEncodeSettings:
    """Re-encode quality matching the export that produced the inputs."""

    width: int = 1920
    height: int = 1080
    fps: int = 24
    speed_mode: str = "balanced"

    @property
    def label(self) -> str:
        return f"{self.width}x{self.height}@{self.fps}fps · {self.speed_mode}"


def resolve_merge_encode_settings(
    settings: dict | None,
    *,
    branch: str = "long",
    pipeline: bool = False,
    width: int | None = None,
    height: int | None = None,
    fps: int | None = None,
    speed_mode: str | None = None,
) -> MergeEncodeSettings:
    """Resolve merge re-encode settings from export tier / explicit overrides."""
    tier = resolve_export_tier_settings(settings, pipeline=pipeline)
    normalized_branch = "reel" if str(branch or "").strip().lower() == "reel" else "long"
    resolution = REEL_EXPORT_RESOLUTION if normalized_branch == "reel" else tier.resolution
    tier_w, tier_h = parse_render_resolution(resolution)
    return MergeEncodeSettings(
        width=max(16, int(width if width is not None else tier_w)),
        height=max(16, int(height if height is not None else tier_h)),
        fps=normalize_export_fps(fps if fps is not None else tier.fps),
        speed_mode=normalize_export_speed_mode(
            speed_mode if speed_mode is not None else tier.speed_mode,
            default=tier.speed_mode,
        ),
    )


def merge_encode_settings_from_context(context: dict | None, *, pipeline: bool = False) -> MergeEncodeSettings:
    raw = dict(context or {})
    settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
    width = raw.get("encode_width")
    height = raw.get("encode_height")
    fps = raw.get("encode_fps")
    speed_mode = raw.get("encode_speed_mode")
    try:
        width_i = int(width) if width is not None else None
    except (TypeError, ValueError):
        width_i = None
    try:
        height_i = int(height) if height is not None else None
    except (TypeError, ValueError):
        height_i = None
    return resolve_merge_encode_settings(
        settings if isinstance(settings, dict) else {},
        branch=str(raw.get("branch") or "long"),
        pipeline=pipeline,
        width=width_i,
        height=height_i,
        fps=fps,
        speed_mode=str(speed_mode) if speed_mode is not None else None,
    )


def _speed_mode_encode_presets(speed_mode: str) -> tuple[str, str]:
    """Return (nvenc_preset, x264_preset) matching gpu_render export."""
    mode = normalize_export_speed_mode(speed_mode, default="balanced")
    if mode == "very_fast":
        return "p1", "ultrafast"
    if mode == "fast":
        return "p3", "superfast"
    if mode == "best_quality":
        return "p7", "medium"
    if mode == "quality":
        return "p5", "veryfast"
    return "p3", "veryfast"


def build_merge_reencode_args(
    *,
    ffmpeg_path: str,
    encode: MergeEncodeSettings,
) -> tuple[list[str], str]:
    """FFmpeg args after ``-i`` for export-matched merge re-encode. Returns (args, codec_label)."""
    from shared.lib.export_bitrate import ffmpeg_vbr_bitrate_args, recommended_vbr_ladder_kbps

    nvenc_preset, x264_preset = _speed_mode_encode_presets(encode.speed_mode)
    width = max(16, int(encode.width))
    height = max(16, int(encode.height))
    width -= width % 2
    height -= height % 2
    fps = normalize_export_fps(encode.fps)
    target_kbps, maxrate_kbps, bufsize_kbps = recommended_vbr_ladder_kbps(
        width, height, fps, encode.speed_mode
    )
    vbr_args = ffmpeg_vbr_bitrate_args(target_kbps, maxrate_kbps, bufsize_kbps)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={fps}"
    )
    args: list[str] = ["-vf", vf]
    use_nvenc = False
    try:
        from visualizer.nvenc_capability import probe_h264_nvenc

        use_nvenc = bool(probe_h264_nvenc(str(ffmpeg_path or "ffmpeg")))
    except Exception:
        use_nvenc = False
    if use_nvenc:
        args += [
            "-c:v",
            "h264_nvenc",
            "-preset",
            nvenc_preset,
            "-rc",
            "vbr",
            *vbr_args,
            "-color_range",
            "pc",
            "-pix_fmt",
            "yuv420p",
        ]
        codec_label = "NVENC"
    else:
        args += [
            "-c:v",
            "libx264",
            "-preset",
            x264_preset,
            *vbr_args,
            "-color_range",
            "pc",
            "-pix_fmt",
            "yuv420p",
        ]
        codec_label = "CPU x264"
    args += [
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
    ]
    return args, codec_label


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
            if is_usable_export_output(target, require_media=True):
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
    """True when size has stopped growing. Ignore mtime — Windows AV/indexer can touch it."""
    path = Path(target_path)
    try:
        if not path.is_file():
            return False
        previous = path.stat()
        if previous.st_size < MIN_VALID_EXPORT_BYTES:
            return False
        with path.open("rb") as handle:
            handle.read(1)
    except OSError:
        return False

    for _ in range(3):
        time.sleep(0.25)
        try:
            current = path.stat()
        except OSError:
            return False
        if current.st_size == previous.st_size and current.st_size >= MIN_VALID_EXPORT_BYTES:
            return True
        previous = current
    return False


def collect_verified_merge_inputs(
    mp4_paths: list[str],
    *,
    run_dir: str = "",
    branch: str = "long",
    ffmpeg_path: str = "",
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_fps: int | float | None = None,
) -> list[str]:
    """Rebuild merge inputs from verified outputs only (never trust expected paths blindly)."""
    from features.video.lib.export_output_validity import export_matches_batch_specs

    def _accept(path: str) -> bool:
        if expected_width and expected_height:
            return export_matches_batch_specs(
                path,
                width=int(expected_width),
                height=int(expected_height),
                fps=float(expected_fps or 0),
                ffmpeg_path=ffmpeg_path,
            )
        return is_usable_export_output(path, ffmpeg_path=ffmpeg_path, require_media=True)

    requested = [str(path).strip() for path in mp4_paths if str(path).strip()]
    verified: list[str] = []
    for path in requested:
        if _accept(path):
            verified.append(path)
    if len(verified) >= 2:
        return verified
    # Fall back to scanning the run folder when explicit paths were stale/mismatched.
    scanned = list_branch_export_outputs(str(run_dir or "").strip(), branch)
    if not scanned:
        return verified
    scanned_set = {Path(path).resolve(): path for path in scanned if _accept(path)}
    ordered: list[str] = []
    seen: set[str] = set()
    for path in requested:
        key = Path(path).resolve()
        match = scanned_set.get(key)
        if match and match not in seen:
            ordered.append(match)
            seen.add(match)
    for path in scanned_set.values():
        if path not in seen:
            ordered.append(path)
            seen.add(path)
    return ordered


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


def _unlink_quiet(target_path: str) -> None:
    try:
        Path(target_path).unlink(missing_ok=True)
    except OSError:
        return


def _probe_media_duration_sec(path: str, *, ffprobe_path: str) -> float:
    from features.video.lib.export_output_validity import _probe_format_duration

    return float(_probe_format_duration(path, ffprobe_path) or 0.0)


def _run_ffmpeg_with_progress(
    *,
    ffmpeg_path: str,
    args: list[str],
    total_duration_sec: float,
    emit: ProgressCallback,
    cancel: Callable[[], bool],
) -> None:
    """Run ffmpeg with ``-progress pipe:1`` and emit 0–100 merge percent."""
    import subprocess
    import threading

    cmd = [ffmpeg_path, "-y", "-nostdin", "-progress", "pipe:1", "-nostats", *args]
    proc = popen_hidden(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )
    err_parts: list[str] = []

    def _drain_stderr() -> None:
        stream = proc.stderr
        if stream is None:
            return
        try:
            for line in stream:
                err_parts.append(line)
        except OSError:
            pass

    drain = threading.Thread(target=_drain_stderr, daemon=True)
    drain.start()
    last_percent = -1
    total = max(0.0, float(total_duration_sec or 0.0))
    stdout = proc.stdout
    try:
        while True:
            if cancel():
                try:
                    proc.kill()
                except OSError:
                    pass
                raise RuntimeError("Video export stopped.")
            if stdout is None:
                break
            line = stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            text = str(line).strip()
            if text.startswith("out_time_ms="):
                raw = text.split("=", 1)[1].strip()
                try:
                    out_ms = int(raw)
                except ValueError:
                    continue
                if total > 0.25:
                    percent = int((out_ms / 1000.0) / total * 100)
                    percent = max(0, min(99, percent))
                else:
                    percent = min(95, max(last_percent + 1, 1))
                if percent != last_percent:
                    last_percent = percent
                    emit(f"Merging… {percent}%", percent)
            elif text == "progress=end":
                last_percent = 100
                emit("Merging… 100%", 100)
    finally:
        try:
            if proc.poll() is None:
                proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass
        drain.join(timeout=2)

    if cancel():
        raise RuntimeError("Video export stopped.")
    code = int(proc.returncode if proc.returncode is not None else 1)
    if code != 0:
        detail = "".join(err_parts).strip()
        raise RuntimeError(detail or f"Video merge exited with code {code}")


def merge_video_outputs(
    *,
    ffmpeg_path: str,
    mp4_paths: list[str],
    target_path: str,
    on_progress: ProgressCallback | None = None,
    cancel_check: Callable[[], bool] | None = None,
    shuffle: bool = True,
    encode: MergeEncodeSettings | None = None,
    match_export_specs: bool = False,
) -> str | None:
    requested = [str(path).strip() for path in mp4_paths if str(path).strip()]
    if len(requested) < 2:
        return None
    if is_valid_export_output(target_path):
        return target_path

    emit = on_progress or (lambda _message, _percent=None: None)
    cancel = cancel_check or (lambda: False)
    resolved_ffmpeg = find_ffmpeg_from_path_hint(ffmpeg_path)
    ffprobe_path = find_ffprobe_from_path_hint(resolved_ffmpeg)
    encode_settings = encode or MergeEncodeSettings()

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    emit("Preparing merge…", 0)
    valid_paths: list[str] = []
    skipped_paths: list[str] = []
    for file_path in requested:
        if cancel():
            raise RuntimeError("Video export stopped.")
        path = Path(file_path)
        try:
            if not path.is_file():
                skipped_paths.append(file_path)
                continue
            stat = path.stat()
            if stat.st_size < MIN_VALID_EXPORT_BYTES:
                skipped_paths.append(file_path)
                continue
            if not _is_file_stable(file_path):
                skipped_paths.append(file_path)
                continue
            if ffprobe_path:
                if not export_media_looks_complete(file_path, ffprobe_path=ffprobe_path):
                    skipped_paths.append(file_path)
                    continue
            elif not is_valid_export_output(file_path):
                skipped_paths.append(file_path)
                continue
            valid_paths.append(file_path)
        except OSError:
            skipped_paths.append(file_path)

    if skipped_paths:
        shown = ", ".join(Path(path).name for path in skipped_paths[:8])
        extra = f" (+{len(skipped_paths) - 8} more)" if len(skipped_paths) > 8 else ""
        emit(f"Skipping {len(skipped_paths)} incomplete MP4 file(s): {shown}{extra}", 2)

    if len(valid_paths) < 2:
        shown = ", ".join(Path(path).name for path in skipped_paths[:8])
        extra = f" (+{len(skipped_paths) - 8} more)" if len(skipped_paths) > 8 else ""
        raise RuntimeError(
            "Merge did not produce a file — fewer than two MP4s were usable after checks "
            f"(found {len(valid_paths)} usable, skipped {len(skipped_paths)}"
            + (f": {shown}{extra}" if skipped_paths else "")
            + "). Open the run folder and confirm the exported videos play, then Merge again."
        )

    emit("Checking stream compatibility…", 4)
    assert_concat_copy_compatible(
        valid_paths,
        ffmpeg_path=resolved_ffmpeg,
        expected_width=int(encode_settings.width) if match_export_specs else None,
        expected_height=int(encode_settings.height) if match_export_specs else None,
        expected_fps=int(encode_settings.fps) if match_export_specs else None,
    )

    original_order = [Path(path).name for path in valid_paths]
    shuffled = list(valid_paths)
    if shuffle:
        random.shuffle(shuffled)
    _write_merge_order_log(target_path, original_order, [Path(path).name for path in shuffled])

    total_duration = 0.0
    if ffprobe_path:
        for path in shuffled:
            total_duration += _probe_media_duration_sec(path, ffprobe_path=ffprobe_path)

    temp_dir = Path(target.parent) / f"camxora-merge-{int(time.time() * 1000)}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        emit("Preparing FFmpeg merge (stream copy)…", 6)
        prepared_inputs = _prepare_merge_inputs(shuffled, temp_dir)
        concat_file_path = temp_dir / "merge-list.txt"
        concat_contents = "\n".join(
            ["ffconcat version 1.0", *[f"file '{_escape_ffconcat_path(path)}'" for path in prepared_inputs]]
        )
        concat_file_path.write_text(f"{concat_contents}\n", encoding="utf-8")

        try:
            _run_ffmpeg_with_progress(
                ffmpeg_path=resolved_ffmpeg,
                args=[
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file_path),
                    "-c",
                    "copy",
                    target_path,
                ],
                total_duration_sec=total_duration,
                emit=emit,
                cancel=cancel,
            )
        except RuntimeError as exc:
            _unlink_quiet(target_path)
            detail = str(exc or "").strip()
            if detail == "Video export stopped.":
                raise
            raise RuntimeError(
                "Lossless merge failed — exports are not concat-compatible for stream copy"
                + (f" ({detail})" if detail else "")
                + ". Re-export the whole batch with one resolution/FPS/speed setting, then merge again."
            ) from exc
        if not is_valid_export_output(target_path):
            _unlink_quiet(target_path)
            raise RuntimeError(
                "Lossless merge did not produce a valid output. "
                "Re-export the batch and try merge again."
            )
        emit("Merge complete.", 100)
        return target_path
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)
