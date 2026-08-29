"""Music view smoke tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.create.widgets.create_header import CreateHeader
from features.music.views.music_view import LOADING_MESSAGE, MusicView
from features.music.widgets.channel_selection_card import (
    CHANNEL_CHIP_HEIGHT,
    CHANNEL_LIST_SPACING,
    _display_channel_name,
)
from features.music.widgets.song_editor_card import SongEditorCard
from shared.models.auth import ProfileResponse
from shared.models.platform import MusicHistoryListResponse, OperationCostsResponse, PromptNameOption, UserSettingsResponse
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import MusicWorkspacePayload


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _payload() -> MusicWorkspacePayload:
    return MusicWorkspacePayload(
        profiles=[
            ProfileResponse(id="profile-ok", user_id="u1", name="Primary Channel"),
            ProfileResponse(id="profile-alt", user_id="u1", name="Secondary Channel"),
        ],
        settings=UserSettingsResponse.model_validate({"imageSourceMode": "ai", "defaultSongCount": 4}),
        description_options=[PromptNameOption(id="desc-1", name="Cinematic Pop")],
        structure_options=[PromptNameOption(id="struct-1", name="Verse Chorus Bridge")],
        mood_options=[PromptNameOption(id="mood-1", name="Hopeful Dawn")],
        history=MusicHistoryListResponse(summary="No history yet."),
        operation_costs=OperationCostsResponse(
            items=[
                __import__("shared.models.platform", fromlist=["OperationCostResponse"]).OperationCostResponse(
                    operation_type="lyric",
                    credits_per_operation=3,
                    available=True,
                )
            ]
        ),
        language_options=[("en", "English")],
        youtube_connections=[],
    )


def test_loading_state(qapp: QApplication) -> None:
    view = MusicView(PlatformApi())
    view.show()
    assert not view._loading_card.isHidden()
    assert view.objectName() == "music_workspace"
    header = view.findChild(CreateHeader)
    assert header is not None
    assert header.objectName() == "CreateHeader"


def test_empty_song_disables_copy_and_rewrite(qapp: QApplication) -> None:
    card = SongEditorCard()
    assert not card._copy_title_btn.isEnabled()
    assert not card._copy_lyrics_btn.isEnabled()
    assert not card._copy_both_btn.isEnabled()
    card.set_polish_enabled(True)
    assert not card._polish_btn.isEnabled()


def test_channel_names_title_case_all_caps() -> None:
    assert _display_channel_name("BASSNOVA") == "Bassnova"
    assert _display_channel_name("Bass Drive") == "Bass Drive"


def test_ten_channel_chips_fit_without_scroll() -> None:
    occupied = 10 * CHANNEL_CHIP_HEIGHT + 9 * CHANNEL_LIST_SPACING
    assert occupied <= 300


def test_loaded_binds_content(qapp: QApplication) -> None:
    view = MusicView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    assert not view._content.isHidden()
    assert view._automation_card.selected_description_id() == "desc-1"


def test_schedule_settings_save_flashes_once_per_debounce_window(qapp: QApplication, monkeypatch) -> None:
    """Regression test: multiple field edits within one 400ms debounce window
    used to each flash/log "Saving music defaults..." even though only one
    _persist_settings() call ever fires — showing up in logs as the same
    save happening 3x in a row and making the app look slower than it is.
    """
    view = MusicView(PlatformApi())
    view.show()
    view._on_loaded(_payload())

    flashes: list[str] = []
    monkeypatch.setattr(view, "_flash_status", lambda message, **_kwargs: flashes.append(message))
    monkeypatch.setattr(view, "_persist_settings", lambda: None)

    view._on_shuffle_changed()
    view._on_mood_shuffle_changed()
    view._music_settings.shuffle_structure = not view._music_settings.shuffle_structure
    view._schedule_settings_save()

    assert flashes.count("Saving music defaults...") == 1


def test_invalid_date_range_disables_generate(qapp: QApplication) -> None:
    view = MusicView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    view._composer.from_date = "2026-06-27"
    view._composer.to_date = "2026-06-25"
    view._refresh_presentation()
    assert not view._automation_card._generate_btn.isEnabled()


def test_server_prompt_defaults_override_stale_local_prefs(qapp: QApplication, tmp_path, monkeypatch) -> None:
    from dataclasses import replace

    from features.music.services.music_local_store import MusicLocalStore, MusicWorkspacePrefs

    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)

    MusicLocalStore().write_workspace_prefs(
        MusicWorkspacePrefs(
            selected_description_id="desc-old",
            selected_structure_id="struct-old",
        )
    )

    payload = replace(
        _payload(),
        settings=UserSettingsResponse.model_validate(
            {
                "imageSourceMode": "ai",
                "defaultSongCount": 4,
                "defaultDescriptionId": "desc-1",
                "defaultStructureId": "struct-1",
                "defaultMoodId": "mood-1",
            }
        ),
    )

    view = MusicView(PlatformApi())
    view.activate_page()
    view._on_loaded(payload)

    assert view._automation_card.selected_description_id() == "desc-1"
    assert view._automation_card.selected_structure_id() == "struct-1"
    assert view._automation_card.selected_mood_id() == "mood-1"


def test_prompt_selection_override_survives_page_revisit(qapp: QApplication) -> None:
    from dataclasses import replace

    payload = replace(
        _payload(),
        description_options=[
            PromptNameOption(id="desc-1", name="Cinematic Pop"),
            PromptNameOption(id="desc-2", name="EDM Workout"),
        ],
        structure_options=[
            PromptNameOption(id="struct-1", name="Verse Chorus Bridge"),
            PromptNameOption(id="struct-2", name="Workout Gym"),
        ],
        mood_options=[
            PromptNameOption(id="mood-1", name="Hopeful Dawn"),
            PromptNameOption(id="mood-2", name="Bittersweet Night"),
        ],
        settings=UserSettingsResponse.model_validate(
            {
                "imageSourceMode": "ai",
                "defaultSongCount": 4,
                "defaultDescriptionId": "desc-1",
                "defaultStructureId": "struct-1",
                "defaultMoodId": "mood-1",
            }
        ),
    )

    view = MusicView(PlatformApi())
    view.activate_page()
    view._on_loaded(payload)
    assert view._automation_card.selected_description_id() == "desc-1"

    view._prompt_selection_touched = True
    view._selected_description_id = "desc-2"
    view._selected_structure_id = "struct-2"
    view._selected_mood_id = "mood-2"
    view._automation_card.set_selected_options("desc-2", "struct-2", "mood-2")
    assert view._automation_card.selected_description_id() == "desc-2"
    assert view._automation_card.selected_structure_id() == "struct-2"
    assert view._automation_card.selected_mood_id() == "mood-2"

    view.deactivate_page()
    view.activate_page()
    view._on_loaded(payload)

    assert view._automation_card.selected_description_id() == "desc-2"
    assert view._automation_card.selected_structure_id() == "struct-2"
    assert view._automation_card.selected_mood_id() == "mood-2"
