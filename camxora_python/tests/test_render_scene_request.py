"""Tests for manual render scene request builders."""

from __future__ import annotations

from pathlib import Path

from features.video.lib.render_scene_request import (
    build_manual_export_output_path,
    build_manual_render_scene_request,
    build_pipeline_export_output_path,
    build_pipeline_render_scene_request,
    is_valid_export_output,
    parse_render_resolution,
    resolve_manual_export_output_dir,
)


def test_parse_render_resolution() -> None:
    assert parse_render_resolution("1920x1080") == (1920, 1080)
    assert parse_render_resolution("invalid") == (1920, 1080)


def test_normalize_export_fps() -> None:
    from features.video.lib.render_scene_request import normalize_export_fps

    assert normalize_export_fps(24) == 24
    assert normalize_export_fps(30) == 30
    assert normalize_export_fps(48) == 48
    assert normalize_export_fps(60) == 60
    assert normalize_export_fps(29) == 30
    assert normalize_export_fps("48") == 48
    assert normalize_export_fps(None) == 24


def test_build_manual_render_scene_request_uses_live_draft_source() -> None:
    scene = build_manual_render_scene_request(
        template={"style": "straight-bars"},
        template_draft={"logoPath": "D:/logo.png"},
        workspace={
            "templateId": "tpl-1",
            "logoPath": "D:/workspace-logo.png",
            "backgroundPath": "D:/bg.jpg",
            "selectedMp3Path": "D:/track.mp3",
            "outputResolution": "1280x720",
        },
    )
    assert scene.mode == "manual"
    assert scene.context.draft_source == "live"
    assert scene.assets.logo_path == "D:/logo.png"
    assert scene.assets.audio_path == "D:/track.mp3"
    assert scene.output.width == 1280
    assert scene.output.height == 720
    assert scene.output.fps == 24


def test_build_manual_render_scene_request_honors_fps() -> None:
    scene = build_manual_render_scene_request(
        template={"style": "straight-bars"},
        template_draft={},
        workspace={"outputResolution": "1920x1080"},
        fps=48,
    )
    assert scene.output.fps == 48


def test_resolve_manual_export_output_dir_prefers_settings() -> None:
    assert (
        resolve_manual_export_output_dir(
            settings={"videoRenderOutputDir": "D:/exports"},
            audio_path="D:/music/track.mp3",
        )
        == "D:/exports"
    )
    assert (
        resolve_manual_export_output_dir(
            settings={},
            audio_path="D:/music/track.mp3",
        )
        == str(Path("D:/music"))
    )


def test_build_manual_export_output_path_includes_stamp() -> None:
    path = build_manual_export_output_path(audio_path="D:/music/track.mp3", output_dir="D:/exports")
    assert Path(path).parent == Path("D:/exports")
    assert Path(path).name.startswith("track_CAMXORA_")
    assert path.endswith(".mp4")


def test_build_pipeline_render_scene_request_uses_saved_draft_source() -> None:
    scene = build_pipeline_render_scene_request(
        template={"style": "straight-bars"},
        workspace={
            "templateId": "template-saved",
            "outputResolution": "1920x1080",
            "logoPath": "D:/saved-logo.png",
            "selectedMp3Path": "D:/workspace-default.mp3",
        },
        run_dir="D:/runs/batch-01",
        background_path="D:/runs/batch-01/background.png",
        branch="long",
        batch_id="batch-01",
        role="primary",
        selected_mp3_path="D:/runs/batch-01/song-a.mp3",
    )
    assert scene.mode == "pipeline"
    assert scene.context.draft_source == "saved"
    assert scene.context.branch == "long"
    assert scene.assets.run_dir == "D:/runs/batch-01"
    assert scene.assets.audio_path == "D:/runs/batch-01/song-a.mp3"
    assert scene.output.fps == 24


def test_pipeline_render_scene_ignores_template_preview_background() -> None:
    """E2E automation must use batch AI background, never template previewBackground."""
    scene = build_pipeline_render_scene_request(
        template={
            "style": "straight-bars",
            "previewBackground": "D:/templates/design-only-bg.png",
            "logoPath": "D:/logo.png",
        },
        workspace={
            "templateId": "tpl-1",
            "outputResolution": "1920x1080",
            "logoPath": "D:/logo.png",
            "backgroundPath": "D:/templates/design-only-bg.png",
        },
        run_dir="D:/runs/batch-01",
        background_path="D:/runs/batch-01/ai-background-16x9.png",
        branch="long",
        batch_id="batch-01",
        role="primary",
    )
    assert scene.assets.background_path == "D:/runs/batch-01/ai-background-16x9.png"
    assert scene.draft.get("backgroundPath") in ("", None)


def test_build_pipeline_render_scene_request_uses_reel_resolution() -> None:
    scene = build_pipeline_render_scene_request(
        template={"style": "straight-bars"},
        workspace={"outputResolution": "3840x2160", "logoPath": ""},
        run_dir="D:/runs/batch-01",
        background_path="D:/runs/batch-01/background.png",
        branch="reel",
        batch_id="batch-01",
        role="primary",
    )
    assert scene.output.width == 1080
    assert scene.output.height == 1920


def test_build_pipeline_export_output_path_reel_suffix() -> None:
    assert (
        build_pipeline_export_output_path(
            mp3_path="D:/runs/song-a.mp3",
            output_dir="D:/runs",
            branch="reel",
        )
        == str(Path("D:/runs/song-a_REEL.mp4"))
    )
    assert (
        build_pipeline_export_output_path(
            mp3_path="D:/runs/song-a.mp3",
            output_dir="D:/runs",
            branch="long",
        )
        == str(Path("D:/runs/song-a.mp4"))
    )


def test_is_valid_export_output_requires_large_file() -> None:
    assert is_valid_export_output("") is False
