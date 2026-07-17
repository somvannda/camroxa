"""Smoke tests for video workspace view."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from features.video.views.video_view import VideoView
from shared.models.desktop import VideoWorkspaceState


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_video_view_mounts(qapp: QApplication) -> None:
    api = MagicMock()
    view = VideoView(api)
    view.show()
    assert view.isVisible()
    view.activate_page()
    view.deactivate_page()


def test_video_view_mounts_from_preloaded_cache(qapp: QApplication) -> None:
    from shared.services.workspace_cache import WorkspaceCache

    cache = WorkspaceCache()
    workspace = VideoWorkspaceState(template_name="Cached Template")
    cache.apply_video_workspace(workspace, {"outputResolution": "1920x1080"})
    api = MagicMock()
    view = VideoView(api, cache=cache)
    assert view._ever_loaded is True
    assert view._workspace is not None
    assert view._workspace.template_name == "Cached Template"
    assert view._loading is False
    assert view._loading_card.isHidden()
    with patch.object(view, "refresh_data") as refresh_mock:
        view.activate_page()
    refresh_mock.assert_not_called()


def test_video_view_mounts_from_settings_cache_without_profiles(qapp: QApplication) -> None:
    from shared.services.workspace_cache import WorkspaceCache

    cache = WorkspaceCache()
    cache.apply_warmup(settings_raw={"outputResolution": "1920x1080"})
    api = MagicMock()
    view = VideoView(api, cache=cache)
    assert view._ever_loaded is True
    assert view._workspace is not None
    assert view._loading_card.isHidden()
    with patch.object(view, "refresh_data") as refresh_mock:
        view.activate_page()
    refresh_mock.assert_not_called()


def test_video_view_skips_reload_when_reactivated(qapp: QApplication) -> None:
    api = MagicMock()
    view = VideoView(api)
    view._ever_loaded = True
    view._workspace = VideoWorkspaceState()
    with patch.object(view, "refresh_data") as refresh_mock:
        view.activate_page()
    refresh_mock.assert_not_called()


def test_video_view_reloads_when_workspace_cache_invalidated(qapp: QApplication) -> None:
    from shared.services.workspace_cache import WorkspaceCache

    cache = WorkspaceCache()
    cache.apply_video_workspace(
        VideoWorkspaceState(template_name="Before Install"),
        {"outputResolution": "1920x1080"},
    )
    api = MagicMock()
    view = VideoView(api, cache=cache)
    assert view._ever_loaded is True
    cache.invalidate_video_workspace()

    with patch.object(view, "refresh_templates_from_store") as refresh_mock:
        view.activate_page()
    refresh_mock.assert_called_once_with()


def test_refresh_templates_from_store_updates_dropdown(qapp: QApplication) -> None:
    from shared.models.desktop import VideoTemplateSummary

    api = MagicMock()
    view = VideoView(api)
    view._workspace = VideoWorkspaceState(
        template_id="tpl-old",
        templates=[VideoTemplateSummary(id="tpl-old", name="Old")],
    )
    view._settings = {"outputResolution": "1920x1080"}

    new_rows = [
        {
            "id": "tpl-old",
            "name": "Old",
            "source": "user",
            "updated_at": "2026-07-15 00:00:00.000",
        },
        {
            "id": "tpl-mkt",
            "name": "Market Drop",
            "source": "marketplace",
            "updated_at": "2026-07-15 00:00:01.000",
        },
    ]
    with (
        patch.object(view._store, "read_templates", return_value=new_rows),
        patch.object(view._left_rail, "set_templates") as set_templates,
    ):
        view.refresh_templates_from_store()

    assert view._workspace is not None
    assert {item.id for item in view._workspace.templates} == {"tpl-old", "tpl-mkt"}
    set_templates.assert_called_once_with(
        [("tpl-old", "Old"), ("tpl-mkt", "Market Drop")],
        "tpl-old",
    )


def test_on_save_succeeded_clears_saving_busy_without_tab_click(qapp: QApplication) -> None:
    """Save success must refresh the left rail so Save leaves 'Saving...' immediately.

    Regression: hydrate/render ran while _saving was still True (badge → Saved),
    then _saving was cleared without set_busy, so the button stayed on Saving...
    until a domain tab click flushed dirty state.
    """
    api = MagicMock()
    view = VideoView(api)
    workspace = VideoWorkspaceState(template_name="Thunder Bass 1", template_id="tpl-1")
    view._saving = True
    view._left_rail.set_busy(saving=True, deleting=False)
    assert view._left_rail._save_btn.text() == "Saving..."

    with (
        patch.object(view, "_hydrate_draft_from_workspace"),
        patch.object(view, "_persist_local_draft_snapshot"),
        patch.object(view, "_render_workspace"),
        patch.object(view, "_schedule_template_server_sync"),
        patch("features.video.views.video_view.emit_shell_status"),
    ):
        view._on_save_succeeded(workspace)

    assert view._saving is False
    assert view._left_rail._save_btn.text() == "Save"
