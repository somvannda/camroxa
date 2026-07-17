"""Pipeline export input resolution — port of videoPipelineInputs.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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


def resolve_video_pipeline_inputs(
    row: ProgressRow | None,
    branch: VideoPipelineBranch,
    profile: ProfileResponse | None = None,
) -> ResolvedVideoPipelineInputs:
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
