from __future__ import annotations

from pathlib import Path

from shared.lib.ffmpeg_paths import resolve_ffmpeg_path
from shared.lib.workspace_defaults import apply_workspace_path_defaults, default_workspace_paths


def test_apply_workspace_path_defaults_creates_folders(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings, patch = apply_workspace_path_defaults({})
    defaults = default_workspace_paths()
    assert settings["downloadsDir"] == defaults["downloadsDir"]
    assert Path(settings["downloadsDir"]).is_dir()
    assert Path(settings["sunoOutputDir"]).is_dir()
    assert Path(settings["mergedDir"]).is_dir()
    assert Path(settings["imageBackgroundSamplesDir"]).is_dir()
    assert Path(settings["imageThumbnailSamplesDir"]).is_dir()
    assert "downloadsDir" in patch


def test_apply_workspace_path_defaults_preserves_user_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    custom = tmp_path / "custom-downloads"
    custom.mkdir()
    settings, patch = apply_workspace_path_defaults({"downloadsDir": str(custom)})
    assert settings["downloadsDir"] == str(custom)
    assert "downloadsDir" not in patch


def test_resolve_ffmpeg_path_prefers_existing_hint(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"bin")
    assert resolve_ffmpeg_path(str(ffmpeg)) == str(ffmpeg)


def test_style_strength_not_required_for_generate(tmp_path: Path) -> None:
    from shared.lib.music_readiness import evaluate_music_readiness
    from shared.models.auth import ProfileResponse
    from shared.models.platform import YouTubeConnectionResponse

    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_text("bin", encoding="utf-8")
    folders = {
        name: tmp_path / name
        for name in ("downloads", "suno", "merged", "bg", "th")
    }
    for folder in folders.values():
        folder.mkdir()
    (folders["bg"] / "one.png").write_bytes(b"png")
    (folders["th"] / "two.png").write_bytes(b"png")

    profile = ProfileResponse(
        id="p1",
        user_id="user-1",
        name="Primary",
        video_template_id="tpl-1",
        youtube_config={
            "visibility": "unlisted",
            "made_for_kids": False,
            "ai_use": True,
            "category": "10",
            "title_template": "{title}",
            "description_template": "{description}",
        },
    )
    report = evaluate_music_readiness(
        selected_profiles=[profile],
        settings={
            "ffmpegPath": str(ffmpeg),
            "downloadsDir": str(folders["downloads"]),
            "sunoOutputDir": str(folders["suno"]),
            "mergedDir": str(folders["merged"]),
            "imageBackgroundSamplesDir": str(folders["bg"]),
            "imageThumbnailSamplesDir": str(folders["th"]),
            "styleStrength": 42,
        },
        youtube_connections=[
            YouTubeConnectionResponse(profile_id="p1", profile_name="Primary", status="connected")
        ],
        bg_sample_count=1,
        th_sample_count=1,
    )
    assert report.generate_ready
    assert not any(item.id == "pref:style_strength" for item in report.items)
