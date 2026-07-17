"""Tests for pipeline export input resolution."""

from __future__ import annotations

from features.video.lib.pipeline_inputs import (
    build_video_pipeline_run_key,
    filter_pipeline_progress_rows,
    resolve_video_pipeline_inputs,
)
from shared.models.auth import ProfileResponse
from shared.models.platform import ProgressRow, ProgressRowMeta


def _sample_row(*, long_ready: bool = True, reel_ready: bool = True) -> ProgressRow:
    return ProgressRow(
        batch="Batch 1",
        run_date="2026-06-29",
        channel="Primary",
        status="waiting",
        music="Ready",
        image="Ready",
        converter="Pending",
        merge="Pending",
        youtube="Pending",
        stage="Converter",
        notes="",
        updated="2026-06-29 12:00:00",
        meta=ProgressRowMeta(
            batch_id="batch-1",
            profile_id="profile-1",
            role="ok",
            run_dir="D:/Music/Primary/2026-06-29",
            source_mode="manual",
            background_16x9_path="D:/Music/Primary/2026-06-29/background-16x9.png",
            background_9x16_path="D:/Music/Primary/2026-06-29/background-9x16.png",
            thumbnail_16x9_path="D:/Music/Primary/2026-06-29/thumbnail-16x9.png",
            thumbnail_9x16_path="D:/Music/Primary/2026-06-29/thumbnail-9x16.png",
            long_ready=long_ready,
            reel_ready=reel_ready,
            expected=1,
            saved=1,
        ),
    )


def test_build_video_pipeline_run_key() -> None:
    row = _sample_row()
    assert build_video_pipeline_run_key(row) == "batch-1:profile-1:ok"


def test_filter_pipeline_progress_rows_requires_run_dir_and_assets() -> None:
    ready_row = _sample_row()
    missing_assets = ProgressRow(
        batch="Batch 2",
        run_date="2026-06-29",
        channel="Primary",
        status="waiting",
        music="Ready",
        image="Ready",
        converter="Pending",
        merge="Pending",
        youtube="Pending",
        stage="Converter",
        notes="",
        updated="2026-06-29 12:00:00",
        meta=ProgressRowMeta(
            batch_id="batch-2",
            profile_id="profile-1",
            role="ok",
            run_dir="D:/Music/Primary/2026-06-29",
        ),
    )
    filtered = filter_pipeline_progress_rows([ready_row, missing_assets])
    assert filtered == [ready_row]


def test_resolve_video_pipeline_inputs_long_branch() -> None:
    profile = ProfileResponse(
        id="profile-1",
        user_id="user-1",
        name="Primary",
        folder_name="Primary",
        run_prefix="PRI",
        video_template_id="video-template-1",
        reel_template_id="reel-template-1",
    )
    result = resolve_video_pipeline_inputs(_sample_row(), "long", profile)
    assert result.ready is True
    assert "background-16x9" in str(result.background_path)
    assert "thumbnail-16x9" in str(result.thumbnail_path)
    assert result.recommended_template_id == "video-template-1"


def test_resolve_video_pipeline_inputs_reel_branch() -> None:
    profile = ProfileResponse(
        id="profile-1",
        user_id="user-1",
        name="Primary",
        folder_name="Primary",
        run_prefix="PRI",
        video_template_id="video-template-1",
        reel_template_id="reel-template-1",
    )
    result = resolve_video_pipeline_inputs(_sample_row(), "reel", profile)
    assert result.ready is True
    assert "background-9x16" in str(result.background_path)
    assert "thumbnail-9x16" in str(result.thumbnail_path)
    assert result.recommended_template_id == "reel-template-1"
