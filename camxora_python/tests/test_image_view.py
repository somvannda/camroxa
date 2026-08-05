"""Image view smoke tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from features.image.views.image_view import LOADING_MESSAGE, ImageView
from shared.models.auth import ProfileResponse, UserMeResponse
from shared.models.platform import ImageJobsListResponse, MusicHistoryListResponse, ProgressListResponse, UserSettingsResponse
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import ImageWorkspacePayload


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _payload() -> ImageWorkspacePayload:
    return ImageWorkspacePayload(
        me=UserMeResponse(
            id="user-1",
            email="user@example.com",
            email_confirmed=True,
            display_name="User",
            credit_balance=50,
        ),
        profiles=[ProfileResponse(id="profile-ok", user_id="u1", name="OK Channel")],
        progress=ProgressListResponse(summary="0"),
        image_jobs=ImageJobsListResponse(items=[]),
        settings=UserSettingsResponse.model_validate(
            {
                "imageBackgroundPrompt": "My base background prompt",
                "imageThumbnailPrompt": "My base thumbnail prompt",
            }
        ),
        music_history=MusicHistoryListResponse(
            batches=[
                __import__("shared.models.platform", fromlist=["MusicHistoryBatch"]).MusicHistoryBatch(
                    batch_id="batch-1",
                    from_date="2026-06-28",
                    to_date="2026-06-28",
                    created_at="2026-06-28T00:00:00Z",
                    updated_at="2026-06-28T00:00:00Z",
                )
            ],
            summary="1 batches loaded",
        ),
    )


def test_loading_state(qapp: QApplication) -> None:
    view = ImageView(PlatformApi())
    view.show()
    assert not view._loading_card.isHidden()


def test_loaded_binds_content(qapp: QApplication) -> None:
    view = ImageView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    assert not view._content.isHidden()
    assert view._controls_card.background_prompt() == "My base background prompt"
    assert view._background_preview is not None


def test_layout_labels_and_manual_generation(qapp: QApplication) -> None:
    view = ImageView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    buttons = view.findChildren(QPushButton)
    labels = {button.text() for button in buttons}
    assert "Clear Queue" in labels
    assert "Manual Generation" in labels
    assert not any("Generate now" in label for label in labels)
    assert view._background_preview.source_mode() == "category"
    assert view._thumbnail_preview.source_mode() == "category"


def test_manual_generation_without_row_prompt_only_requires_prompt(qapp: QApplication) -> None:
    view = ImageView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    view._controls_card.clear_selection()
    view._background_preview.set_source_mode("prompt_only")
    view._controls_card.set_prompts("", "thumb")
    view._on_manual_generation("background")
    assert not view._error_banner.isHidden()
    assert "Background:" in view._error_banner._label.text()


def test_manual_generation_without_row_category_starts_worker(qapp: QApplication) -> None:
    view = ImageView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    view._controls_card.clear_selection()
    view._background_preview.set_source_mode("category")
    view._controls_card.set_prompts("", "thumb")
    view._on_manual_generation("background")
    assert view._error_banner.isHidden()
    assert view._standalone_worker is not None


def test_background_poll_does_not_reset_source_mode(qapp: QApplication) -> None:
    view = ImageView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    view._background_preview.set_source_mode("prompt_only")
    view._refresh_quiet = True
    # Simulate a quiet poll delivering server settings still at category.
    view._on_loaded(_payload())
    assert view._background_preview.source_mode() == "prompt_only"
    assert view.poll_interval_ms >= 12_000


def test_preflight_blocks_prompt_only_empty(qapp: QApplication) -> None:
    from shared.models.platform import ImageJobListItem

    view = ImageView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    view._controls_card.set_prompts("", "thumb ok")
    view._background_preview.set_source_mode("prompt_only")
    view._image_jobs = [
        ImageJobListItem(
            id="job-bg",
            kind="background",
            channel_role="long",
            status="success",
            batch_id="batch-1",
        )
    ]
    message = view._preflight_regenerate(["job-bg"])
    assert message is not None
    assert "Background:" in message
