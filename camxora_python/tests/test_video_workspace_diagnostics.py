"""Tests for video workspace diagnostics builder."""

from __future__ import annotations

from features.video.lib.pipeline_inputs import ResolvedVideoPipelineInputs
from features.video.lib.video_workspace_diagnostics import (
    build_video_workspace_diagnostics,
    serialize_diagnostics_payload,
)
from shared.models.desktop import VideoExportState, VideoPlaybackState, VideoWorkspaceState


def test_build_video_workspace_diagnostics_marks_unsaved_template() -> None:
    model = build_video_workspace_diagnostics(
        workspace=VideoWorkspaceState(
            template_id="tpl-1",
            background_path="D:/bg.png",
            selected_mp3_path="D:/track.mp3",
            export=VideoExportState(),
        ),
        template_name_draft="My Template",
        workspace_dirty=True,
        draft_dirty_map={"spectrum": True, "background": False, "logo": False, "particles": False, "text": False},
        active_domain_tab="spectrum",
        saving=False,
        playback=VideoPlaybackState(is_ready=True),
        preview_track_path="D:/track.mp3",
        pipeline_branch="long",
        pipeline_inputs=None,
        preview_lifecycle_status="running",
        preview_lifecycle_message="GPU preview compositor is running.",
        preview_remount_pending=False,
        gpu_preview_available=True,
        performance={"frameMs": 16.7, "fps": 60.0},
        export_gate_active=0,
        export_gate_limit=2,
    )
    assert model.save_status_label == "Local Draft Pending"
    assert model.can_reset_local_draft is True
    assert any(item.label == "Spectrum" and item.dirty for item in model.dirty_domains)
    assert "16.7 ms" in model.performance_label


def test_build_video_workspace_diagnostics_error_points_at_preview_gl_log() -> None:
    model = build_video_workspace_diagnostics(
        workspace=VideoWorkspaceState(export=VideoExportState()),
        template_name_draft="Template",
        workspace_dirty=False,
        draft_dirty_map={domain: False for domain in ("spectrum", "background", "logo", "particles", "text")},
        active_domain_tab="background",
        saving=False,
        playback=VideoPlaybackState(),
        preview_track_path="",
        pipeline_branch="long",
        pipeline_inputs=None,
        preview_lifecycle_status="error",
        preview_lifecycle_message="initializeGL failed: no context",
        preview_remount_pending=False,
        gpu_preview_available=True,
    )
    assert model.preview_needs_attention is True
    assert any("preview-gl-diag.log" in item for item in model.preview_guidance_items)

    model = build_video_workspace_diagnostics(
        workspace=VideoWorkspaceState(export=VideoExportState()),
        template_name_draft="Template",
        workspace_dirty=False,
        draft_dirty_map={domain: False for domain in ("spectrum", "background", "logo", "particles", "text")},
        active_domain_tab="background",
        saving=False,
        playback=VideoPlaybackState(),
        preview_track_path="",
        pipeline_branch="long",
        pipeline_inputs=ResolvedVideoPipelineInputs(
            branch="long",
            ready=False,
            run_dir=None,
            source_mode=None,
            background_path=None,
            thumbnail_path=None,
            recommended_template_id=None,
            recommended_template_label="Long template",
        ),
        preview_lifecycle_status="unsupported",
        preview_lifecycle_message="",
        preview_remount_pending=False,
        gpu_preview_available=False,
    )
    assert model.preview_needs_attention is True
    assert "GPU preview" in model.preview_guidance_title


def test_serialize_diagnostics_payload_roundtrip() -> None:
    model = build_video_workspace_diagnostics(
        workspace=VideoWorkspaceState(template_id="tpl-1", export=VideoExportState()),
        template_name_draft="Template",
        workspace_dirty=False,
        draft_dirty_map={domain: False for domain in ("spectrum", "background", "logo", "particles", "text")},
        active_domain_tab="spectrum",
        saving=False,
        playback=VideoPlaybackState(),
        preview_track_path="",
        pipeline_branch="reel",
        pipeline_inputs=None,
        preview_lifecycle_status="running",
        preview_lifecycle_message="",
        preview_remount_pending=False,
        gpu_preview_available=False,
    )
    from features.video.lib.video_workspace_diagnostics import build_video_workspace_diagnostics_payload

    payload = build_video_workspace_diagnostics_payload(
        workspace=VideoWorkspaceState(template_id="tpl-1", export=VideoExportState()),
        template_name_draft="Template",
        active_domain_tab="spectrum",
        workspace_dirty=False,
        draft_dirty_map={domain: False for domain in ("spectrum", "background", "logo", "particles", "text")},
        playback=VideoPlaybackState(),
        preview_track_path="",
        pipeline_branch="reel",
        pipeline_inputs=None,
        preview_runtime_nonce=2,
        preview_lifecycle_status="running",
        preview_lifecycle_message="",
        performance={"frameMs": 0.0, "fps": 0.0},
        export_gate_active=0,
        export_gate_limit=1,
        diagnostics=model,
    )
    text = serialize_diagnostics_payload(payload)
    assert '"templateId": "tpl-1"' in text
    assert '"previewRuntimeNonce": 2' in text
