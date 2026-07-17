"""Tests for pipeline export merge helpers."""

from __future__ import annotations

from pathlib import Path

from features.video.lib.pipeline_merge import (
    build_merged_output_path,
    is_auto_merge_enabled_for_branch,
    list_branch_export_outputs,
    normalize_merge_role,
    safe_batch_suffix,
)
from features.video.lib.render_scene_request import MIN_VALID_EXPORT_BYTES


def test_safe_batch_suffix_parses_standard_batch_id() -> None:
    assert safe_batch_suffix("batch-2026-07-08-12-34") == "2026-07-08_12_34"


def test_safe_batch_suffix_sanitizes_freeform_text() -> None:
    assert safe_batch_suffix("run #1") == "run_1"


def test_normalize_merge_role() -> None:
    assert normalize_merge_role("primary") == "PRIMARY"
    assert normalize_merge_role("alt") == "SECONDARY"
    assert normalize_merge_role("secondary") == "SECONDARY"


def test_is_auto_merge_enabled_for_branch() -> None:
    settings = {"autoMergeAfterVideo": True, "autoReelAfterVideo": True}
    assert is_auto_merge_enabled_for_branch(settings, "long") is True
    assert is_auto_merge_enabled_for_branch(settings, "reel") is True
    assert is_auto_merge_enabled_for_branch({"autoMergeAfterVideo": True}, "reel") is False
    assert is_auto_merge_enabled_for_branch({}, "long") is False


def test_is_auto_merge_reads_truthy_string_settings() -> None:
    """Live API settings may stringify booleans; must still enable long merge."""
    settings = {"autoMergeAfterVideo": "true", "autoReelAfterVideo": "true"}
    assert is_auto_merge_enabled_for_branch(settings, "long") is True
    assert is_auto_merge_enabled_for_branch(settings, "reel") is True


def test_build_merged_output_path() -> None:
    long_path = build_merged_output_path(
        output_dir="/tmp/run",
        batch_id="batch-2026-07-08-1-2",
        role="primary",
        branch="long",
    )
    reel_path = build_merged_output_path(
        output_dir="/tmp/run",
        batch_id="batch-2026-07-08-1-2",
        role="alt",
        branch="reel",
    )
    assert long_path.endswith("MERGED_PRIMARY_2026-07-08_1_2.mp4")
    assert reel_path.endswith("MERGED_REEL_SECONDARY_2026-07-08_1_2.mp4")


def test_list_branch_export_outputs_filters_reel_and_long(tmp_path: Path) -> None:
    valid = tmp_path / "track.mp4"
    valid.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    reel = tmp_path / "track_REEL.mp4"
    reel.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    merged = tmp_path / "MERGED_PRIMARY_batch.mp4"
    merged.write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    tiny = tmp_path / "tiny.mp4"
    tiny.write_bytes(b"x")

    long_outputs = list_branch_export_outputs(str(tmp_path), "long")
    reel_outputs = list_branch_export_outputs(str(tmp_path), "reel")

    assert long_outputs == [str(valid)]
    assert reel_outputs == [str(reel)]
