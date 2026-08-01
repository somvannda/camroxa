from __future__ import annotations

from pathlib import Path

from shared.lib.ffmpeg_paths import resolve_ffmpeg_path
from shared.lib.workspace_defaults import (
    apply_workspace_path_defaults,
    default_workspace_paths,
    ensure_directory,
)


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


def test_ensure_directory_does_not_raise_when_uncreatable(tmp_path: Path) -> None:
    # Seen in the wild: %LOCALAPPDATA% points at a Windows profile folder that
    # doesn't exist and can't be created by the process (permission denied).
    # A file blocking the target path reproduces the same "can't mkdir here"
    # shape cross-platform without needing OS-level permission tricks.
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    target = blocker / "nested"

    result = ensure_directory(str(target))

    assert result == str(target)
    assert not target.exists()


def test_ensure_directory_caches_known_uncreatable_path(tmp_path: Path, monkeypatch) -> None:
    # Regression test: Settings page re-derives current settings on every
    # keystroke via _dirty_tabs() -> build_system_settings_patch() ->
    # apply_workspace_path_defaults() -> ensure_directory(). Retrying a real
    # mkdir(parents=True) against a permanently broken path on every
    # keystroke turned a fast crash into a silent, repeating multi-level
    # failure cascade that froze the UI thread. Repeated calls to the same
    # known-bad path must only attempt the syscall once.
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    target = str(blocker / "nested")

    call_count = 0
    original_mkdir = Path.mkdir

    def _counting_mkdir(self, *args, **kwargs):
        nonlocal call_count
        if str(self) == target:
            call_count += 1
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _counting_mkdir)

    ensure_directory(target)
    ensure_directory(target)
    ensure_directory(target)

    assert call_count == 1


def test_apply_workspace_path_defaults_survives_uncreatable_root(tmp_path: Path, monkeypatch) -> None:
    blocker = tmp_path / "blocked-root"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(blocker))

    # Must not raise even though every default path lives under an
    # uncreatable root — this previously crashed every settings/navigation
    # action that touched workspace defaults.
    settings, patch = apply_workspace_path_defaults({})
    assert settings["downloadsDir"]
    assert "downloadsDir" in patch


def test_apply_workspace_path_defaults_preserves_user_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    custom = tmp_path / "custom-downloads"
    custom.mkdir()
    settings, patch = apply_workspace_path_defaults({"downloadsDir": str(custom)})
    assert settings["downloadsDir"] == str(custom)
    assert "downloadsDir" not in patch


def test_apply_workspace_path_defaults_heals_stale_cross_machine_path(tmp_path: Path, monkeypatch) -> None:
    # Reproduces the reported bug: downloadsDir etc. are saved account-wide
    # (server-side), so a path saved from a *different* machine/Windows
    # profile gets replayed here and can never be created on this machine
    # (simulated by a file blocking the target, same shape as "parent isn't
    # a directory I can create things under").
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    blocker = tmp_path / "someone-elses-profile"
    blocker.write_text("not a directory", encoding="utf-8")
    stale_path = str(blocker / "Camxora" / "Media" / "Downloads")

    settings, patch = apply_workspace_path_defaults({"downloadsDir": stale_path})

    defaults = default_workspace_paths()
    assert settings["downloadsDir"] == defaults["downloadsDir"]
    assert Path(settings["downloadsDir"]).is_dir()
    assert patch["downloadsDir"] == defaults["downloadsDir"]


def test_apply_workspace_path_defaults_heals_low_disk_space_path(tmp_path: Path, monkeypatch) -> None:
    # Reproduces the "E:\Suno lands on a near-full USB stick" report: the
    # synced path is a perfectly valid, creatable directory (mkdir/is_dir
    # both succeed) but the drive has almost no free space, so every
    # download/export into it would silently produce 0-byte files.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    low_space_dir = tmp_path / "near-full-drive" / "Suno"
    low_space_dir.mkdir(parents=True)

    import shared.lib.workspace_defaults as workspace_defaults_module

    monkeypatch.setattr(
        workspace_defaults_module,
        "has_sufficient_free_space",
        lambda _path, minimum_bytes=0: False,
    )

    settings, patch = apply_workspace_path_defaults({"sunoOutputDir": str(low_space_dir)})

    defaults = default_workspace_paths()
    assert settings["sunoOutputDir"] == defaults["sunoOutputDir"]
    assert patch["sunoOutputDir"] == defaults["sunoOutputDir"]


def test_apply_workspace_defaults_seeds_fast_speed_when_unset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings, patch = apply_workspace_path_defaults({})
    assert settings["videoExportSpeedMode"] == "fast"
    assert patch["videoExportSpeedMode"] == "fast"

    settings2, patch2 = apply_workspace_path_defaults({"videoExportSpeedMode": "balanced"})
    assert settings2["videoExportSpeedMode"] == "balanced"
    assert "videoExportSpeedMode" not in patch2


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
