"""End-to-end local workspace isolation across account switches."""

from __future__ import annotations

import json
from pathlib import Path

from features.image.services.image_local_store import ImageLocalStore, ImageWorkspacePrefs
from features.music.services.music_local_store import MusicLocalStore, MusicWorkspacePrefs
from features.workflow.services.workflow_local_store import WorkflowLocalStore, WorkflowWorkspacePrefs
from shared.lib.app_paths import (
    get_image_workspace_prefs_path,
    get_music_workspace_prefs_path,
    get_workflow_workspace_prefs_path,
)
from shared.services.local_user_scope import activate_local_user_scope, deactivate_local_user_scope
from shared.services.secure_storage import SecureStorage


class _MemoryStorage(SecureStorage):
    def __init__(self) -> None:
        super().__init__(store_path=Path("memory-only") / "store.json")
        self._data = {}

    def _load(self) -> None:
        return

    def _save(self) -> None:
        return


def test_workspace_prefs_isolate_and_restore_per_account(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)

    storage = _MemoryStorage()

    activate_local_user_scope("user-a", storage)
    MusicLocalStore().write_workspace_prefs(
        MusicWorkspacePrefs(from_date="2026-01-01", to_date="2026-01-07", selected_description_id="desc-a")
    )
    ImageLocalStore().write_workspace_prefs(
        ImageWorkspacePrefs(from_date="2026-02-01", to_date="2026-02-05", selected_queue_key="queue-a")
    )
    WorkflowLocalStore().write_workspace_prefs(
        WorkflowWorkspacePrefs(from_date="2026-03-01", to_date="2026-03-03", selected_key="lane-a")
    )

    activate_local_user_scope("user-b", storage)
    assert MusicLocalStore().read_workspace_prefs() is None
    assert ImageLocalStore().read_workspace_prefs() is None
    assert WorkflowLocalStore().read_workspace_prefs() is None

    MusicLocalStore().write_workspace_prefs(
        MusicWorkspacePrefs(from_date="2026-04-01", to_date="2026-04-02")
    )
    assert get_music_workspace_prefs_path().parent.name == "user-b"

    activate_local_user_scope("user-a", storage)
    restored_music = MusicLocalStore().read_workspace_prefs()
    restored_image = ImageLocalStore().read_workspace_prefs()
    restored_workflow = WorkflowLocalStore().read_workspace_prefs()
    assert restored_music is not None
    assert restored_music.from_date == "2026-01-01"
    assert restored_music.selected_description_id == "desc-a"
    assert restored_image is not None
    assert restored_image.selected_queue_key == "queue-a"
    assert restored_workflow is not None
    assert restored_workflow.selected_key == "lane-a"

    deactivate_local_user_scope()


def test_pull_workspace_prefs_from_settings_applies_remote_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)

    activate_local_user_scope("user-a", _MemoryStorage())
    local_music = get_music_workspace_prefs_path()
    local_music.parent.mkdir(parents=True, exist_ok=True)
    local_music.write_text(
        json.dumps({"version": 1, "fromDate": "2026-01-01", "updatedAt": 1}),
        encoding="utf-8",
    )

    from shared.services.workspace_prefs_sync import pull_workspace_prefs_from_settings

    remote = {
        "desktopWorkspacePrefs": {
            "version": 1,
            "updatedAt": 9_999_999_999_999,
            "music": {"version": 1, "fromDate": "2026-06-01", "toDate": "2026-06-07"},
            "image": {"version": 1, "fromDate": "2026-06-02", "toDate": "2026-06-03"},
            "workflow": {"version": 1, "fromDate": "2026-06-04", "toDate": "2026-06-05"},
        }
    }
    assert pull_workspace_prefs_from_settings("user-a", remote) is True
    assert json.loads(get_music_workspace_prefs_path().read_text(encoding="utf-8"))["fromDate"] == "2026-06-01"
    assert json.loads(get_image_workspace_prefs_path().read_text(encoding="utf-8"))["fromDate"] == "2026-06-02"
    assert json.loads(get_workflow_workspace_prefs_path().read_text(encoding="utf-8"))["fromDate"] == "2026-06-04"

    deactivate_local_user_scope()
