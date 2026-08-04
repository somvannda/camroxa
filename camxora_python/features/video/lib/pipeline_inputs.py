"""Pipeline export input resolution — port of videoPipelineInputs.ts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared.lib.channel_asset_paths import (
    compute_long_ready,
    compute_reel_ready,
    count_channel_mp3_files,
    resolve_local_channel_asset_paths,
)
from shared.models.auth import ProfileResponse
from shared.models.platform import ProgressRow

VideoPipelineBranch = Literal["long", "reel"]


@dataclass(frozen=True)
class ResolvedVideoPipelineInputs:
    branch: VideoPipelineBranch
    ready: bool
    run_dir: str | None
    source_mode: str | None
    background_path: str | None
    thumbnail_path: str | None
    recommended_template_id: str | None
    recommended_template_label: str


def build_video_pipeline_run_key(row: ProgressRow) -> str:
    return f"{row.meta.batch_id}:{row.meta.profile_id}:{row.meta.role}"


def filter_pipeline_progress_rows(rows: list[ProgressRow]) -> list[ProgressRow]:
    filtered: list[ProgressRow] = []
    for row in rows:
        meta = row.meta
        if not str(meta.run_dir or "").strip():
            continue
        if not any(
            str(path or "").strip()
            for path in (
                meta.background_16x9_path,
                meta.background_9x16_path,
                meta.thumbnail_16x9_path,
                meta.thumbnail_9x16_path,
            )
        ):
            continue
        filtered.append(row)
    return filtered


def resolve_local_video_pipeline_inputs(
    row: ProgressRow | None,
    branch: VideoPipelineBranch,
    profile: ProfileResponse | None = None,
) -> ResolvedVideoPipelineInputs:
    """Resolve pipeline assets from the local run folder (disk truth for automation)."""
    meta = row.meta if row is not None else None
    is_long = branch == "long"
    run_dir = str(meta.run_dir or "").strip() if meta is not None else ""
    if run_dir:
        from shared.lib.device_workspace_paths import local_run_dir_for_disk
        from shared.services.file_service import sanitize_local_path

        run_dir = local_run_dir_for_disk(sanitize_local_path(run_dir))
    recommended_template_id = (
        (profile.video_template_id if is_long else profile.reel_template_id) if profile is not None else None
    )
    if not run_dir:
        return ResolvedVideoPipelineInputs(
            branch=branch,
            ready=False,
            run_dir=None,
            source_mode=meta.source_mode if meta is not None else None,
            background_path=None,
            thumbnail_path=None,
            recommended_template_id=recommended_template_id,
            recommended_template_label="Long template" if is_long else "Reel template",
        )

    assets = resolve_local_channel_asset_paths(run_dir, channel_role=meta.role if meta is not None else None)
    background_path = assets["background_16x9_path"] if is_long else assets["background_9x16_path"]
    thumbnail_path = assets["thumbnail_16x9_path"] if is_long else assets["thumbnail_9x16_path"]
    # Export needs background only; thumbnail is optional (YouTube upload).
    ready = compute_long_ready(assets) if is_long else compute_reel_ready(assets)
    if ready and (not background_path or not Path(str(background_path)).is_file()):
        ready = False

    return ResolvedVideoPipelineInputs(
        branch=branch,
        ready=ready,
        run_dir=run_dir,
        source_mode=meta.source_mode if meta is not None else None,
        background_path=background_path,
        thumbnail_path=thumbnail_path,
        recommended_template_id=recommended_template_id,
        recommended_template_label="Long template" if is_long else "Reel template",
    )


def local_audio_downloads_ready(row: ProgressRow) -> bool:
    """True when local MP3 files satisfy expected count (disk truth for export/automation)."""
    from shared.lib.progress_local_sync import local_mp3_files_ready

    meta = row.meta
    expected = max(1, int(meta.expected or 0))
    run_dir = str(meta.run_dir or "").strip()
    if run_dir:
        from shared.lib.device_workspace_paths import local_run_dir_for_disk
        from shared.services.file_service import sanitize_local_path

        run_dir = local_run_dir_for_disk(sanitize_local_path(run_dir))
    if run_dir and local_mp3_files_ready(row):
        return True

    downloaded = max(0, int(meta.saved or 0))
    download_ready = max(0, int(meta.download_ready or 0))
    pending_download = max(0, int(meta.download_pending or 0))
    if not (
        downloaded >= expected
        and download_ready >= expected
        and pending_download <= 0
    ):
        return False

    if not run_dir:
        return True
    return count_channel_mp3_files(run_dir, meta.role) >= expected


def resolve_video_pipeline_inputs(
    row: ProgressRow | None,
    branch: VideoPipelineBranch,
    profile: ProfileResponse | None = None,
) -> ResolvedVideoPipelineInputs:
    """Resolve pipeline assets from batch progress meta (AI backgrounds), never template preview."""
    meta = row.meta if row is not None else None
    is_long = branch == "long"
    background_path = (meta.background_16x9_path if is_long else meta.background_9x16_path) if meta else None
    thumbnail_path = (meta.thumbnail_16x9_path if is_long else meta.thumbnail_9x16_path) if meta else None
    recommended_template_id = (
        (profile.video_template_id if is_long else profile.reel_template_id) if profile is not None else None
    )
    return ResolvedVideoPipelineInputs(
        branch=branch,
        ready=bool(meta.long_ready if is_long else meta.reel_ready) if meta is not None else False,
        run_dir=meta.run_dir if meta is not None else None,
        source_mode=meta.source_mode if meta is not None else None,
        background_path=background_path,
        thumbnail_path=thumbnail_path,
        recommended_template_id=recommended_template_id,
        recommended_template_label="Long template" if is_long else "Reel template",
    )
