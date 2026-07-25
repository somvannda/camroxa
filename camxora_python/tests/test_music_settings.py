"""Music settings helpers."""

from __future__ import annotations

from shared.lib.music_settings import build_music_settings_patch, build_music_settings_state


def test_build_music_settings_state_reads_use_content_pools() -> None:
    state = build_music_settings_state({"useContentPools": True, "uniqueOpening": True})
    assert state.use_content_pools is True
    assert state.unique_opening is True


def test_build_music_settings_state_reads_shuffle_structure() -> None:
    state = build_music_settings_state({"shuffleStructure": True})
    assert state.shuffle_structure is True
    assert build_music_settings_state({}).shuffle_structure is False


def test_build_music_settings_state_reads_shuffle_mood() -> None:
    state = build_music_settings_state({"shuffleMood": True, "defaultMoodId": "mood-1"})
    assert state.shuffle_mood is True
    assert state.default_mood_id == "mood-1"
    assert build_music_settings_state({}).shuffle_mood is False


def test_build_music_settings_patch_writes_use_content_pools() -> None:
    state = build_music_settings_state({})
    state.use_content_pools = True
    patch = build_music_settings_patch(state)
    assert patch["useContentPools"] is True


def test_build_music_settings_patch_writes_shuffle_structure() -> None:
    state = build_music_settings_state({})
    state.shuffle_structure = True
    patch = build_music_settings_patch(state)
    assert patch["shuffleStructure"] is True


def test_build_music_settings_patch_writes_shuffle_mood() -> None:
    state = build_music_settings_state({})
    state.shuffle_mood = True
    patch = build_music_settings_patch(state)
    assert patch["shuffleMood"] is True
