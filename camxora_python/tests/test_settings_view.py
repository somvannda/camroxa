"""Settings view smoke tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.settings.views.settings_view import LOADING_MESSAGE, SettingsView, TAB_LABELS
from shared.models.auth import ProfileResponse, UserMeResponse
from shared.models.platform import PromptNameOption, UserSettingsResponse
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import SettingsWorkspacePayload


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _payload() -> SettingsWorkspacePayload:
    return SettingsWorkspacePayload(
        me=UserMeResponse(
            id="user-1",
            email="boss@example.com",
            email_confirmed=True,
            display_name="Boss",
            credit_balance=100,
            profile_allowance=5,
            channel_profile_count=1,
        ),
        profiles=[
            ProfileResponse(
                id="profile-1",
                user_id="user-1",
                name="Boss Primary",
                folder_name="boss-primary",
                run_prefix="boss",
            )
        ],
        settings=UserSettingsResponse.model_validate({"ffmpegPath": "C:/ffmpeg/bin/ffmpeg.exe"}),
        description_options=[PromptNameOption(id="d1", name="EDM / Workout Gym")],
        structure_options=[PromptNameOption(id="s1", name="Festival Big Drop")],
        mood_options=[PromptNameOption(id="m1", name="Hopeful Dawn")],
        youtube_connections=[],
    )


def test_loading_state(qapp: QApplication) -> None:
    view = SettingsView(PlatformApi())
    view.show()
    assert not view._loading_card.isHidden()


def test_profile_template_combos_refresh_on_catalog_change(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    from features.video.services import video_local_store as video_local_store_mod
    from shared.lib import app_paths
    from shared.services.video_template_catalog import emit_video_template_catalog_changed

    user_templates = tmp_path / "video-templates.json"
    prefs = tmp_path / "prefs.json"
    monkeypatch.setattr(app_paths, "get_user_video_templates_path", lambda: user_templates)
    monkeypatch.setattr(app_paths, "get_video_workspace_prefs_path", lambda: prefs)
    monkeypatch.setattr(video_local_store_mod, "get_user_video_templates_path", lambda: user_templates)
    monkeypatch.setattr(video_local_store_mod, "get_video_workspace_prefs_path", lambda: prefs)
    user_templates.write_text("[]", encoding="utf-8")
    prefs.write_text("{}", encoding="utf-8")

    view = SettingsView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    assert view._profile_video_template.findData("tpl-live") < 0

    user_templates.write_text(
        '[{"id":"tpl-live","name":"Live Template","source":"user","template":{}}]',
        encoding="utf-8",
    )
    emit_video_template_catalog_changed()
    qapp.processEvents()

    assert view._profile_video_template.findData("tpl-live") >= 0
    assert view._profile_video_template.itemText(view._profile_video_template.findData("tpl-live")) == "Live Template"


def test_profile_search_filters_list(qapp: QApplication) -> None:
    view = SettingsView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    view._profile_search.setText("electro")
    view._bind_profiles_tab()
    assert view._profile_list.count() == 0


def test_resolve_profile_media_paths_never_calls_network(qapp: QApplication, monkeypatch, tmp_path) -> None:
    """Regression test: selecting a profile used to synchronously download a
    multi-megabyte logo/cover over the network, freezing the whole UI on any
    profile switch until the (possibly slow/unreliable) download finished.
    _resolve_profile_media_paths() must stay cache-only and never touch the
    network; downloading now happens in a background worker instead.
    """
    import features.settings.views.settings_view as settings_view_mod
    from shared.lib.settings_workspace import ProfileDraft

    monkeypatch.setattr(settings_view_mod, "get_profile_media_cache_dir", lambda: tmp_path)

    def _boom(*_args, **_kwargs):
        raise AssertionError("network download must not be called from _resolve_profile_media_paths")

    view = SettingsView(PlatformApi())
    monkeypatch.setattr(view._api, "download_profile_logo", _boom)
    monkeypatch.setattr(view._api, "download_profile_cover", _boom)

    profile = ProfileResponse(
        id="profile-cache-1",
        user_id="user-1",
        name="Cache Test",
        folder_name="cache-test",
        run_prefix="cache",
        logo_path="remote-logo-key",
    )
    draft = ProfileDraft(logo_path="remote-logo-key", cover_path="remote-cover-key")

    resolved = view._resolve_profile_media_paths(profile, draft)

    # Nothing cached locally yet, so both remote identifiers pass through unchanged.
    assert resolved.logo_path == "remote-logo-key"
    assert resolved.cover_path == "remote-cover-key"


def test_bind_profiles_tab_starts_background_download_for_uncached_media(
    qapp: QApplication, monkeypatch, tmp_path
) -> None:
    import features.settings.views.settings_view as settings_view_mod

    monkeypatch.setattr(settings_view_mod, "get_profile_media_cache_dir", lambda: tmp_path)

    view = SettingsView(PlatformApi())
    view.show()
    payload = _payload()
    payload.profiles[0].logo_path = "remote-logo-key"
    view._on_loaded(payload)
    view._selected_profile_key = payload.profiles[0].id
    view._bind_profiles_tab()

    assert view._profile_media_cache_worker is not None
    view._profile_media_cache_worker.wait(2000)


def test_settings_view_resets_when_account_cache_mismatch(qapp: QApplication, monkeypatch) -> None:
    from shared.services.workspace_cache import WorkspaceCache
    from shared.workers.data_workers import SettingsWorkspaceWorker

    cache = WorkspaceCache()
    cache.apply_settings_workspace(
        me=UserMeResponse(
            id="user-2",
            email="other@example.com",
            email_confirmed=True,
            display_name="Other",
            credit_balance=0,
        ),
        profiles=[ProfileResponse(id="profile-2", user_id="user-2", name="Other Profile")],
        settings_raw={"ffmpegPath": "C:/ffmpeg/bin/ffmpeg.exe"},
        description_options=[PromptNameOption(id="d1", name="EDM / Workout Gym")],
        structure_options=[PromptNameOption(id="s1", name="Festival Big Drop")],
        mood_options=[PromptNameOption(id="m1", name="Hopeful Dawn")],
        youtube_connections=[],
    )
    view = SettingsView(PlatformApi(), cache=cache)
    view.show()
    view._loaded_user_id = "user-1"
    view._ever_loaded = True
    assert view._account_cache_mismatch() is True

    started: list[int] = []

    def _track_start(self) -> None:  # noqa: ANN001
        started.append(1)

    monkeypatch.setattr(SettingsWorkspaceWorker, "start", _track_start)
    view.activate_page()
    assert view._ever_loaded is False
    assert view._loaded_user_id is None
    assert not view._loading_card.isHidden()
    assert started == [1]


def test_settings_skips_refresh_when_cache_fresh(qapp: QApplication, monkeypatch) -> None:
    from shared.services.workspace_cache import WorkspaceCache
    from shared.workers import data_workers

    cache = WorkspaceCache()
    cache.apply_settings_workspace(
        profiles=[ProfileResponse(id="profile-1", user_id="user-1", name="Boss Primary")],
        settings_raw={"ffmpegPath": "C:/ffmpeg/bin/ffmpeg.exe"},
        description_options=[PromptNameOption(id="d1", name="EDM / Workout Gym")],
        structure_options=[PromptNameOption(id="s1", name="Festival Big Drop")],
        mood_options=[PromptNameOption(id="m1", name="Hopeful Dawn")],
        youtube_connections=[],
    )
    view = SettingsView(PlatformApi(), cache=cache)
    view.show()
    view._on_loaded(_payload())
    started: list[int] = []

    def _track_start(self) -> None:  # noqa: ANN001
        started.append(1)

    monkeypatch.setattr(data_workers.SettingsWorkspaceWorker, "start", _track_start)
    view.refresh_data()
    assert started == []
