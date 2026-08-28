"""Helpers for Create Auto Image / Auto Video / Merge automation."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Callable

from features.video.lib.pipeline_merge import (
    MergeEncodeSettings,
    build_merged_output_path,
    merge_video_outputs,
)
from features.video.services.export_job import find_ffmpeg_from_path_hint
from features.video.services.video_local_store import VideoLocalStore
from shared.lib.create_generate import VERSION_1, VERSION_2, CreateGeneratePlan, safe_image_filename
from shared.models.platform import ImageGenerationRequest

ProgressFn = Callable[[str], None]
_MERGED_RE = re.compile(r"^MERGED_", re.IGNORECASE)
_BG_RE = re.compile(r"background", re.IGNORECASE)


def save_image_base64(data: str, dest: Path) -> None:
    raw = base64.b64decode(str(data or "").strip())
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)


def generate_day_images(
    api: Any,
    plan: CreateGeneratePlan,
    *,
    day_index: int,
    on_progress: ProgressFn | None = None,
) -> list[Path]:
    """Generate bg + thumbnail into Version 1 and Version 2 for one planned day."""
    emit = on_progress or (lambda _msg: None)
    written: list[Path] = []
    root = Path(plan.save_folder)
    jobs = (
        (VERSION_1, "background", "1920x1080"),
        (VERSION_1, "thumbnail", "1280x720"),
        (VERSION_2, "background", "1920x1080"),
        (VERSION_2, "thumbnail", "1280x720"),
    )
    for folder_name, kind, resolution in jobs:
        filename = safe_image_filename(kind, day_index=day_index, planned_days=plan.planned_days)
        dest = root / folder_name / filename
        emit(f"Generating {folder_name}/{filename}…")
        from shared.lib.create_generate import image_prompt_for

        response = api.generate_image(
            ImageGenerationRequest(
                prompt=image_prompt_for(plan, kind=kind, day_index=day_index),
                kind=kind,
                resolution=resolution,
            )
        )
        if not response.image_base64:
            raise RuntimeError(f"Image generation returned empty data for {filename}.")
        save_image_base64(response.image_base64, dest)
        written.append(dest)
    return written


def find_background_image(folder: Path) -> Path | None:
    if not folder.is_dir():
        return None
    images = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    if not images:
        return None
    for path in images:
        if _BG_RE.search(path.name):
            return path
    return sorted(images, key=lambda item: item.name.lower())[0]


def template_payload(template_id: str) -> dict[str, Any] | None:
    normalized = str(template_id or "").strip()
    if not normalized:
        return None
    store = VideoLocalStore()
    for item in store.read_templates():
        if str(item.get("id") or "").strip() != normalized:
            continue
        payload = item.get("template")
        if isinstance(payload, dict):
            return dict(payload)
        return dict(item)
    return None


def list_version_mp3s(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return [
        str(path)
        for path in sorted(folder.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() == ".mp3"
    ]


def list_mergeable_mp4s(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return [
        str(path)
        for path in sorted(folder.iterdir(), key=lambda item: item.name.lower())
        if path.is_file()
        and path.suffix.lower() == ".mp4"
        and not _MERGED_RE.match(path.name)
    ]


def merge_version_folder(
    folder: Path,
    *,
    role: str,
    on_progress: ProgressFn | None = None,
) -> Path | None:
    emit = on_progress or (lambda _msg: None)
    mp4s = list_mergeable_mp4s(folder)
    if len(mp4s) < 2:
        emit(f"Skip merge in {folder.name}: need at least two videos.")
        return None
    ffmpeg = find_ffmpeg_from_path_hint("ffmpeg")
    target = build_merged_output_path(
        output_dir=str(folder),
        batch_id="create",
        role=role,
        branch="long",
    )
    emit(f"Merging {folder.name} ({len(mp4s)} videos)…")
    merged = merge_video_outputs(
        ffmpeg_path=ffmpeg,
        mp4_paths=mp4s,
        target_path=target,
        on_progress=lambda message, _percent=None: emit(str(message)),
        shuffle=False,
        encode=MergeEncodeSettings(),
        match_export_specs=False,
    )
    return Path(merged) if merged else None


def export_version_videos(
    folder: Path,
    *,
    template_id: str,
    settings: dict[str, Any] | None = None,
    on_progress: ProgressFn | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[Path]:
    """Best-effort Auto Video: render each MP3 with the chosen template + folder background."""
    emit = on_progress or (lambda _msg: None)
    stop = should_stop or (lambda: False)
    template = template_payload(template_id)
    if template is None:
        emit(f"Skip Auto Video for {folder.name}: template not selected.")
        return []
    background = find_background_image(folder)
    if background is None:
        emit(f"Skip Auto Video for {folder.name}: no background image yet.")
        return []
    mp3s = list_version_mp3s(folder)
    if not mp3s:
        emit(f"Skip Auto Video for {folder.name}: no MP3 files.")
        return []

    from features.video.lib.render_scene_request import build_pipeline_long_output_path
    from features.video.services.export_coordinator import (
        PipelineCoordinatorExportRequest,
        run_subprocess_export,
    )
    from features.video.services.export_job import ExportSettings, find_ffmpeg_from_path_hint as find_ff

    prefs = VideoLocalStore().read_prefs()
    logo_path = str(prefs.get("logoPath") or "").strip()
    resolved_settings = dict(settings or {})
    width = int(resolved_settings.get("videoRenderWidth") or 1920)
    height = int(resolved_settings.get("videoRenderHeight") or 1080)
    fps = int(resolved_settings.get("videoExportFps") or resolved_settings.get("exportFps") or 30)
    speed_mode = str(resolved_settings.get("exportSpeedMode") or "fast")
    ffmpeg_path = find_ff(str(resolved_settings.get("ffmpegPath") or "ffmpeg"))
    written: list[Path] = []
    for index, mp3_path in enumerate(mp3s, start=1):
        if stop():
            raise RuntimeError("Generate cancelled.")
        output_path = build_pipeline_long_output_path(
            mp3_path=mp3_path,
            output_dir=str(folder),
        )
        emit(f"Auto Video {folder.name}: {index}/{len(mp3s)}…")
        export_settings = ExportSettings(
            ffmpeg_path=ffmpeg_path,
            output_dir=str(folder),
            output_path=output_path,
            fps=fps,
            width=width,
            height=height,
            speed_mode=speed_mode,
        )
        request = PipelineCoordinatorExportRequest(
            mp3_path=mp3_path,
            template=dict(template),
            background_path=str(background),
            logo_path=logo_path,
            settings=export_settings,
            speed_mode=speed_mode,
        )
        code, _message, _job = run_subprocess_export(request)
        if code == 0 and Path(output_path).is_file():
            written.append(Path(output_path))
        else:
            emit(f"Auto Video failed for {Path(mp3_path).name} (code {code}).")
    return written
