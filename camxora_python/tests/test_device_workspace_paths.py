"""Per-device media path store + Suno download path remapping."""

from __future__ import annotations

import json
from pathlib import Path

from shared.lib.device_workspace_paths import (
    album_leaf_relative,
    device_path_patch_against_cloud,
    load_device_workspace_paths,
    overlay_device_paths,
    path_is_under_base,
    persist_device_paths_from_settings,
    remap_suno_download_paths,
    resolve_local_suno_output_dir,
    save_device_workspace_paths,
)
from shared.lib.music_download_utils import remap_pending_download_target
from shared.lib.workspace_defaults import apply_workspace_path_defaults, default_workspace_paths
from shared.models.platform import PendingMusicDownloadTarget
from shared.services.local_user_scope import activate_local_user_scope, deactivate_local_user_scope
from shared.services.secure_storage import SecureStorage
from shared.services.workspace_defaults_sync import ensure_workspace_defaults


class _MemoryStorage(SecureStorage):
    def __init__(self) -> None:
        super().__init__(store_path=Path("memory-only") / "store.json")
        self._data = {}

    def _load(self) -> None:
        return

    def _save(self) -> None:
        return


def _scope_user(tmp_path: Path, monkeypatch, user_id: str = "user-a") -> None:
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)
    activate_local_user_scope(user_id, _MemoryStorage())


def test_device_paths_round_trip(tmp_path: Path, monkeypatch) -> None:
    _scope_user(tmp_path, monkeypatch)
    saved = save_device_workspace_paths({"sunoOutputDir": str(tmp_path / "Suno"), "downloadsDir": ""})
    assert saved["sunoOutputDir"] == str(tmp_path / "Suno")
    assert "downloadsDir" not in saved
    loaded = load_device_workspace_paths()
    assert loaded["sunoOutputDir"] == str(tmp_path / "Suno")
    deactivate_local_user_scope()


def test_overlay_device_paths_wins_over_cloud(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _scope_user(tmp_path, monkeypatch)
    local_suno = tmp_path / "local-suno"
    local_suno.mkdir()
    persist_device_paths_from_settings({"sunoOutputDir": str(local_suno)})

    cloud = {"sunoOutputDir": r"C:\Users\OtherPC\AppData\Local\Camxora\Media\Suno"}
    merged = overlay_device_paths(cloud)
    assert merged["sunoOutputDir"] == str(local_suno)
    deactivate_local_user_scope()


def test_apply_defaults_prefers_device_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _scope_user(tmp_path, monkeypatch)
    local_suno = tmp_path / "E-drive-Suno"
    local_suno.mkdir()
    persist_device_paths_from_settings({"sunoOutputDir": str(local_suno)})

    settings, patch = apply_workspace_path_defaults(
        {"sunoOutputDir": str(tmp_path / "cloud-appdata-suno")}
    )
    assert settings["sunoOutputDir"] == str(local_suno)
    assert "sunoOutputDir" not in patch
    deactivate_local_user_scope()


def test_ensure_workspace_defaults_persists_local_and_patches_cloud_diff(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _scope_user(tmp_path, monkeypatch)
    local_suno = tmp_path / "machine-suno"
    local_suno.mkdir()
    persist_device_paths_from_settings({"sunoOutputDir": str(local_suno)})

    patches: list[dict] = []

    class _Api:
        def patch_settings(self, patch: dict) -> None:
            patches.append(dict(patch))

    cloud = {"sunoOutputDir": str(tmp_path / "other-machine-suno")}
    merged = ensure_workspace_defaults(settings_raw=cloud, api=_Api(), persist=True)

    assert merged["sunoOutputDir"] == str(local_suno)
    assert patches and patches[0]["sunoOutputDir"] == str(local_suno)
    stored = json.loads(
        (tmp_path / "users" / "user-a" / "device-workspace-paths.json").read_text(encoding="utf-8")
    )
    assert stored["sunoOutputDir"] == str(local_suno)
    deactivate_local_user_scope()


def test_device_path_patch_against_cloud() -> None:
    patch = device_path_patch_against_cloud(
        {"sunoOutputDir": r"E:\SUNO", "downloadsDir": r"E:\DL"},
        {"sunoOutputDir": r"C:\Users\PC\AppData\Local\Camxora\Media\Suno", "downloadsDir": r"E:\DL"},
    )
    assert patch == {"sunoOutputDir": r"E:\SUNO"}


def test_album_leaf_relative_keeps_channel_and_album() -> None:
    rel = album_leaf_relative(r"C:\Users\PC\AppData\Local\Camxora\Media\Suno\ok_channel\2026-08-03_album")
    assert rel == Path("ok_channel") / "2026-08-03_album"


def test_remap_suno_download_paths_rebases_onto_local(tmp_path: Path) -> None:
    local = tmp_path / "Suno"
    foreign = Path(r"C:\Users\Other\AppData\Local\Camxora\Media\Suno\ch1\2026-08-03_hit")
    target = foreign / "song_OK.mp3"
    new_out, new_target = remap_suno_download_paths(str(foreign), str(target), str(local))
    assert new_out == str(local / "ch1" / "2026-08-03_hit")
    assert new_target == str(local / "ch1" / "2026-08-03_hit" / "song_OK.mp3")
    assert not path_is_under_base(str(foreign), str(local))
    assert path_is_under_base(new_out, str(local))


def test_remap_pending_download_target(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _scope_user(tmp_path, monkeypatch)
    local = tmp_path / "Suno"
    local.mkdir()
    persist_device_paths_from_settings({"sunoOutputDir": str(local)})

    target = PendingMusicDownloadTarget(
        download_url="https://example.test/a.mp3",
        downloaded=False,
        output_dir=r"C:\Users\Other\AppData\Local\Camxora\Media\Suno\alt\2026-08-03_x",
        target_path=r"C:\Users\Other\AppData\Local\Camxora\Media\Suno\alt\2026-08-03_x\a_Alt.mp3",
    )
    remapped = remap_pending_download_target(target)
    assert remapped.output_dir == str(local / "alt" / "2026-08-03_x")
    assert remapped.target_path == str(local / "alt" / "2026-08-03_x" / "a_Alt.mp3")
    assert resolve_local_suno_output_dir() == str(local)
    deactivate_local_user_scope()


def test_local_run_dir_for_disk_rebases_server_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _scope_user(tmp_path, monkeypatch)
    local = tmp_path / "Suno"
    local.mkdir()
    persist_device_paths_from_settings({"sunoOutputDir": str(local)})
    from shared.lib.device_workspace_paths import local_run_dir_for_disk

    remapped = local_run_dir_for_disk(
        r"C:\Users\Other\AppData\Local\Camxora\Media\Suno\ch\2026-08-03_album"
    )
    assert remapped == str(local / "ch" / "2026-08-03_album")
    deactivate_local_user_scope()


def test_local_mp3_files_ready_uses_remapped_run_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _scope_user(tmp_path, monkeypatch)
    local = tmp_path / "Suno"
    album = local / "ch" / "2026-08-03_album"
    album.mkdir(parents=True)
    (album / "1. Track_OK.mp3").write_bytes(b"mp3")
    persist_device_paths_from_settings({"sunoOutputDir": str(local)})

    from shared.lib.progress_local_sync import local_mp3_files_ready
    from shared.models.platform import ProgressRow, ProgressRowMeta

    row = ProgressRow(
        batch="b1",
        run_date="2026-08-03",
        channel="ch",
        status="running",
        music="ready",
        image="pending",
        converter="pending",
        merge="pending",
        youtube="pending",
        stage="video",
        notes="",
        updated="",
        meta=ProgressRowMeta(
            batch_id="b1",
            profile_id="p1",
            role="OK",
            expected=1,
            run_dir=r"C:\Users\Other\AppData\Local\Camxora\Media\Suno\ch\2026-08-03_album",
        ),
    )
    assert local_mp3_files_ready(row) is True
    deactivate_local_user_scope()


def test_empty_device_store_still_seeds_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _scope_user(tmp_path, monkeypatch)
    settings, patch = apply_workspace_path_defaults({})
    defaults = default_workspace_paths()
    assert settings["sunoOutputDir"] == defaults["sunoOutputDir"]
    assert "sunoOutputDir" in patch
    deactivate_local_user_scope()
