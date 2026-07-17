"""Music local store tests."""

from __future__ import annotations

from pathlib import Path

from features.music.services.music_local_store import MusicLocalStore, MusicWorkspacePrefs


def test_music_local_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "music-workspace.json"
    store = MusicLocalStore(path=path)
    prefs = MusicWorkspacePrefs(
        from_date="2026-07-11",
        to_date="2026-07-12",
        primary_profile_ids=["profile-a"],
        secondary_profile_ids=["profile-b"],
        selected_description_id="desc-1",
        selected_structure_id="struct-1",
    )
    store.write_workspace_prefs(prefs)
    loaded = store.read_workspace_prefs()
    assert loaded is not None
    assert loaded.from_date == "2026-07-11"
    assert loaded.to_date == "2026-07-12"
    assert loaded.primary_profile_ids == ["profile-a"]
    assert loaded.secondary_profile_ids == ["profile-b"]
    assert loaded.selected_description_id == "desc-1"
    assert loaded.selected_structure_id == "struct-1"
