"""Tests for workflow step derivation."""

from shared.lib.video_runtime_inspection import ProgressRuntimePresentation
from shared.models.platform import ProgressRow, ProgressRowMeta
from features.workflow.lib.workflow_steps import (
    build_current_focus,
    build_workflow_steps,
    format_branch_copy,
    format_role_label,
    format_upload_status,
    lane_needs_attention,
    resolve_run_status_label,
    run_includes_reel,
    state_label,
)


def _row(**overrides: object) -> ProgressRow:
    meta_overrides = overrides.pop("meta", {})  # type: ignore[misc]
    meta = ProgressRowMeta(
        batch_id="batch-1",
        profile_id="profile-1",
        role="primary",
        expected=5,
        saved=2,
        **meta_overrides,
    )
    defaults = dict(
        batch="abc123",
        run_date="2026-07-07",
        channel="Primary",
        status="Generating",
        music="2/5",
        image="PENDING",
        converter="Missing",
        merge="Pending",
        youtube="—",
        stage="Music",
        notes="In progress",
        updated="14:00:00",
        meta=meta,
    )
    defaults.update(overrides)
    return ProgressRow(**defaults)  # type: ignore[arg-type]


def test_build_workflow_steps_for_music_stage() -> None:
    steps = build_workflow_steps(_row())
    assert steps[0].key == "music"
    assert steps[0].state == "running"
    assert steps[0].percent == 40


def test_format_role_label() -> None:
    assert format_role_label("secondary") == "Secondary"
    assert format_role_label("primary") == "Primary"


def test_build_current_focus_music_download_pending() -> None:
    focus = build_current_focus(_row(meta={"download_pending": 3}))
    assert "3 remaining desktop MP3 download(s)" in focus


def test_resolve_run_status_label_partial_converter() -> None:
    row = _row(
        stage="Converter",
        status="Completed",
        converter="Long 1/2 · Reel 0/2",
        meta={"background_9x16_path": "D:/bg.png"},
    )
    assert resolve_run_status_label("Converter", "Completed", row) == "In Progress"


def test_resolve_run_status_label_completed_only_when_done() -> None:
    row = _row(stage="Done", status="Completed")
    assert resolve_run_status_label("Done", "Completed", row) == "Completed"
    row = _row(
        stage="Merger",
        status="Completed",
        merge="Long merged · Reel pending",
        meta={"background_9x16_path": "D:/bg.png"},
    )
    assert resolve_run_status_label("Merger", "Completed", row) == "In Progress"


def test_format_upload_status_not_started() -> None:
    row = _row(youtube="—", stage="YouTube", status="Completed")
    assert format_upload_status(row) == "Not started"


def test_lane_needs_attention_includes_image_blockers() -> None:
    row = _row(
        stage="Converter",
        status="Ready",
        meta={
            "bg_total": 2,
            "bg_ready": 1,
            "th_total": 2,
            "th_ready": 2,
        },
    )
    assert lane_needs_attention(row) is True


def test_lane_needs_attention_includes_merge_pending() -> None:
    row = _row(stage="Merger", status="Partial", merge="Long merged · Reel pending")
    runtime = ProgressRuntimePresentation(
        converter="Long 2/2 · Reel 2/2",
        merge="Long merged · Reel pending",
        stage="Merger",
        status="Partial",
        notes="",
        converter_percent=100,
        merge_percent=50,
    )
    assert lane_needs_attention(row, runtime) is True


def test_build_workflow_steps_partial_state() -> None:
    row = _row(
        stage="Converter",
        status="Partial",
        converter="Long 1/2 · Reel 0/2",
        meta={"background_9x16_path": "D:/bg.png"},
    )
    runtime = ProgressRuntimePresentation(
        converter="Long 1/2 · Reel 0/2",
        merge="Pending",
        stage="Converter",
        status="Partial",
        notes="partial",
        converter_percent=25,
        merge_percent=0,
    )
    steps = build_workflow_steps(row, runtime)
    converter = next(step for step in steps if step.key == "converter")
    assert converter.state == "partial"


def test_run_includes_reel_from_9x16_assets() -> None:
    row = _row(meta={"background_9x16_path": "D:/runs/bg-9x16.png"})
    assert run_includes_reel(row) is True


def test_run_excludes_reel_without_signals() -> None:
    row = _row(
        converter="Long Ready · Reel Missing",
        merge="Long merged · Reel pending",
        meta={"long_ready": True, "reel_ready": False},
    )
    assert run_includes_reel(row) is False


def test_format_branch_copy_strips_reel() -> None:
    assert format_branch_copy("Long 2/2 · Reel 0/2", include_reel=False) == "Long 2/2"
    assert format_branch_copy("Long completed · Reel pending", include_reel=False) == "Long completed"


def test_long_only_merge_ready_when_reel_not_included() -> None:
    row = _row(
        stage="Merger",
        status="Completed",
        converter="Long 2/2 · Reel 0/2",
        merge="Long merged · Reel pending",
        meta={"long_ready": True},
    )
    assert resolve_run_status_label("Merger", "Completed", row, include_reel=False) == "Completed"


def test_build_workflow_steps_hides_reel_in_details() -> None:
    row = _row(
        stage="Converter",
        status="Partial",
        converter="Long 1/2 · Reel 0/2",
        meta={"long_ready": True},
    )
    steps = build_workflow_steps(row)
    converter = next(step for step in steps if step.key == "converter")
    assert "Reel" not in converter.details[0]
    assert "Long 1/2" in converter.details[0]


def test_build_current_focus_long_only_image() -> None:
    focus = build_current_focus(_row(stage="Image", status="Rendering", meta={"long_ready": False}))
    assert "long background" in focus
    assert "reel" not in focus.lower()


def test_state_label_vocabulary() -> None:
    assert state_label("inactive") == "Not started"
    assert state_label("running") == "In progress"
    assert state_label("done") == "Done"
    assert state_label("partial") == "Partial"
    assert state_label("failed") == "Failed"
