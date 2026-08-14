"""Tests for per-account local workspace scoping."""

from __future__ import annotations

import json
from pathlib import Path

from shared.lib.app_paths import (
    get_music_workspace_prefs_path,
    get_profile_media_cache_dir,
    get_video_draft_store_dir,
)
from shared.services.local_user_scope import (
    activate_local_user_scope,
    deactivate_local_user_scope,
    get_user_workspace_dir,
)
from shared.services.secure_storage import LAST_USER_ID_KEY, SecureStorage


class _MemoryStorage(SecureStorage):
    def __init__(self) -> None:
        super().__init__(store_path=Path("memory-only") / "store.json")
        self._data = {}

    def _load(self) -> None:
        return

    def _save(self) -> None:
        return


def test_scoped_paths_follow_active_user(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)

    activate_local_user_scope("user-a", _MemoryStorage())
    assert get_user_workspace_dir() == tmp_path / "users" / "user-a"
    assert get_music_workspace_prefs_path() == tmp_path / "users" / "user-a" / "camxora-music-workspace.json"
    assert get_video_draft_store_dir() == tmp_path / "users" / "user-a" / "video-drafts"
    assert get_profile_media_cache_dir() == tmp_path / "users" / "user-a" / "profile-media"

    activate_local_user_scope("user-b", _MemoryStorage())
    assert get_music_workspace_prefs_path().parent.name == "user-b"

    deactivate_local_user_scope()
    assert get_music_workspace_prefs_path().parent == tmp_path


def test_legacy_workspace_migrates_into_first_user(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)

    legacy_music = tmp_path / "camxora-music-workspace.json"
    legacy_music.write_text(json.dumps({"version": 1, "fromDate": "2026-01-01"}), encoding="utf-8")
    (tmp_path / "profile-media").mkdir()
    (tmp_path / "profile-media" / "p1").mkdir()

    storage = _MemoryStorage()
    activate_local_user_scope("account-1", storage)

    assert not legacy_music.exists()
    migrated = tmp_path / "users" / "account-1" / "camxora-music-workspace.json"
    assert migrated.is_file()
    assert json.loads(migrated.read_text(encoding="utf-8"))["fromDate"] == "2026-01-01"
    assert (tmp_path / "users" / "account-1" / "profile-media" / "p1").is_dir()
    assert storage.get(LAST_USER_ID_KEY) == "account-1"


def test_second_user_does_not_inherit_first_user_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)

    storage = _MemoryStorage()
    activate_local_user_scope("user-a", storage)
    user_a_music = get_music_workspace_prefs_path()
    user_a_music.parent.mkdir(parents=True, exist_ok=True)
    user_a_music.write_text(json.dumps({"version": 1, "fromDate": "2026-02-01"}), encoding="utf-8")

    activate_local_user_scope("user-b", storage)
    user_b_music = get_music_workspace_prefs_path()
    assert user_b_music != user_a_music
    assert not user_b_music.is_file()


def test_legacy_device_workspace_paths_migrate_when_scoped_already_has_files(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    storage = _MemoryStorage()
    activate_local_user_scope("account-1", storage)
    scoped_music = tmp_path / "users" / "account-1" / "camxora-music-workspace.json"
    scoped_music.parent.mkdir(parents=True, exist_ok=True)
    scoped_music.write_text(json.dumps({"version": 1}), encoding="utf-8")

    (tmp_path / "device-workspace-paths.json").write_text(
        json.dumps({"sunoOutputDir": r"D:\Suno Generated"}),
        encoding="utf-8",
    )

    activate_local_user_scope("account-1", storage)
    migrated = tmp_path / "users" / "account-1" / "device-workspace-paths.json"
    assert migrated.is_file()
    assert json.loads(migrated.read_text(encoding="utf-8"))["sunoOutputDir"] == r"D:\Suno Generated"
    assert not (tmp_path / "device-workspace-paths.json").exists()
    deactivate_local_user_scope()
