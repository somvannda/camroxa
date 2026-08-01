from __future__ import annotations

import json
import time
from pathlib import Path

from shared.services.workspace_prefs_sync import (
    apply_workspace_snapshot,
    build_local_workspace_snapshot,
    build_settings_patch_from_local,
    extract_remote_snapshot,
    pull_workspace_prefs_from_settings,
    remote_is_newer,
)


def test_apply_workspace_snapshot_drops_stale_cross_machine_video_paths(tmp_path: Path, monkeypatch) -> None:
    # Reproduces the same bug class fixed in workspace_defaults.py, but for
    # video workspace prefs (background/logo image, selected MP3, MP3
    # folder), which are synced account-wide via desktopWorkspacePrefs. A
    # snapshot pulled down after being written on a different machine can
    # carry absolute paths that don't exist here.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    real_mp3_dir = tmp_path / "real-mp3s"
    real_mp3_dir.mkdir()
    real_bg = tmp_path / "real-bg.png"
    real_bg.write_bytes(b"png")

    snapshot = {
        "version": 1,
        "updatedAt": 1000,
        "video": {
            "backgroundPath": str(real_bg),
            "logoPath": "C:\\Users\\SomeoneElse\\logo.png",
            "selectedMp3Path": "C:\\Users\\SomeoneElse\\track.mp3",
            "mp3Directory": str(real_mp3_dir),
            "outputResolution": "1920x1080",
        },
    }

    apply_workspace_snapshot("user-1", snapshot)

    from shared.lib.app_paths import get_video_workspace_prefs_path

    written = json.loads(get_video_workspace_prefs_path("user-1").read_text(encoding="utf-8"))
    assert written["backgroundPath"] == str(real_bg)
    assert written["mp3Directory"] == str(real_mp3_dir)
    assert "logoPath" not in written
    assert "selectedMp3Path" not in written
    assert written["outputResolution"] == "1920x1080"


def test_apply_workspace_snapshot_keeps_valid_same_machine_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"png")

    snapshot = {"video": {"logoPath": str(logo)}}
    apply_workspace_snapshot("user-2", snapshot)

    from shared.lib.app_paths import get_video_workspace_prefs_path

    written = json.loads(get_video_workspace_prefs_path("user-2").read_text(encoding="utf-8"))
    assert written["logoPath"] == str(logo)


def test_apply_workspace_snapshot_skips_write_when_all_video_paths_invalid(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    snapshot = {"video": {"backgroundPath": "Z:\\nowhere\\bg.png"}}
    apply_workspace_snapshot("user-3", snapshot)

    from shared.lib.app_paths import get_video_workspace_prefs_path

    assert not get_video_workspace_prefs_path("user-3").exists()


def test_remote_is_newer_compares_timestamps() -> None:
    assert remote_is_newer({"updatedAt": 1}, {"updatedAt": 2})
    assert not remote_is_newer({"updatedAt": 2}, {"updatedAt": 1})


def test_extract_remote_snapshot_parses_json_string() -> None:
    payload = {"desktopWorkspacePrefs": json.dumps({"video": {"outputResolution": "1280x720"}})}
    remote = extract_remote_snapshot(payload)
    assert remote == {"video": {"outputResolution": "1280x720"}}


def test_extract_remote_snapshot_returns_none_for_missing_key() -> None:
    assert extract_remote_snapshot({}) is None
    assert extract_remote_snapshot(None) is None


def test_build_settings_patch_from_local_empty_without_user(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.services.workspace_prefs_sync.get_active_user_id",
        lambda: None,
    )
    assert build_local_workspace_snapshot() == {}
    assert build_settings_patch_from_local() == {}


def test_pull_workspace_prefs_from_settings_applies_newer_remote(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings_raw = {
        "desktopWorkspacePrefs": {
            "updatedAt": int(time.time() * 1000) + 10_000_000,
            "video": {"outputResolution": "1280x720"},
        }
    }
    applied = pull_workspace_prefs_from_settings("user-4", settings_raw)
    assert applied is True

    from shared.lib.app_paths import get_video_workspace_prefs_path

    written = json.loads(get_video_workspace_prefs_path("user-4").read_text(encoding="utf-8"))
    assert written["outputResolution"] == "1280x720"
