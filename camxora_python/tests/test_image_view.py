"""Image view smoke tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from features.create.widgets.create_header import CreateHeader
from features.create.widgets.studio_panel import NestedPanel
from features.image.views.image_view import LOADING_MESSAGE, ImageView
from features.image.widgets.controls_queue_card import (
    _COL_ROLE,
    _QUEUE_ROW_HEIGHT,
    ControlsQueueCard,
)
from features.image.widgets.preview_card import PreviewCard
from shared.lib.image_workspace import QueueRow
from shared.models.auth import ProfileResponse, UserMeResponse
from shared.models.platform import (
    ImageJobListItem,
    ImageJobsListResponse,
    MusicHistoryListResponse,
    ProgressListResponse,
    UserSettingsResponse,
)
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import ImageWorkspacePayload


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _close_qt_widgets(qapp: QApplication):
    yield
    for widget in list(qapp.topLevelWidgets()):
        widget.hide()
        widget.close()
        widget.deleteLater()
    qapp.processEvents()


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
    assert view.objectName() == "image_workspace"
    header = view.widget().findChild(CreateHeader)
    assert header is not None
    assert header.objectName() == "CreateHeader"


def test_loaded_binds_content(qapp: QApplication) -> None:
    view = ImageView(PlatformApi())
    view.show()
    view._on_loaded(_payload())
    assert not view._content.isHidden()
    assert view._controls_card.background_prompt() == "My base background prompt"
    assert view._background_preview is not None
    album_card = view.findChild(QFrame, "ImageAlbumCard")
    assert album_card is not None
    assert view._inspector_album.parentWidget() is album_card
    assert view._inspector_meta.parentWidget() is album_card


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
    assert view._error_banner.isHidden()
    assert "Background:" in view._error_banner._label.text()


def test_row_errors_go_to_shell_footer(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "features.image.views.image_view.emit_shell_status",
        lambda message, tone="neutral": seen.append((str(message), str(tone))),
    )
    view = ImageView(PlatformApi())
    view._publish_footer_detail(
        "TH error: Waiting for background image output from job 855a3276 · BG sample: x.png"
    )
    assert view._error_banner.isHidden()
    assert view._controls_card._footer_detail.text() == "BG sample: x.png"
    assert seen[-1] == ("TH error: Waiting for background image output from job 855a3276", "error")


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


def _png_bytes(width: int, height: int) -> bytes:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0x101F32)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def test_preview_pixmap_does_not_inflate_card_width(qapp: QApplication) -> None:
    card = PreviewCard("Background Preview", "placeholder")
    card.resize(320, 420)
    card.show()
    qapp.processEvents()
    before = card.width()
    card.set_image_bytes(_png_bytes(1920, 1080))
    qapp.processEvents()
    assert card.width() <= before + 8
    assert card._preview.sizeHint().width() <= 320


def test_queue_table_compact_rows_and_summary_card(qapp: QApplication) -> None:
    card = ControlsQueueCard()
    assert card._queue_count.isHidden()
    assert not any(label.text() == "QUEUE ITEMS" for label in card.findChildren(QLabel))
    assert card.layout().itemAt(0).widget() is card._summary_card
    assert card.layout().indexOf(card._table) > card.layout().indexOf(card._summary_card)
    assert len(card._summary_counts.findChildren(NestedPanel)) == 5
    card.set_footer_detail("Ready · 2 tracks in batch · Version 1/album")
    assert card._footer_detail.text() == "Ready · Version 1/album"
    assert "tracks in batch" not in card._footer_detail.text()
    card.set_footer_detail(
        "TH error: Waiting for background image output from job 855a3276 · BG sample: x.png"
    )
    assert card._footer_detail.text() == "BG sample: x.png"
    assert "TH error" not in card._footer_detail.text()
    card.set_queue_summary("Rows 8 · Pending 1 · Running 1 · Failed 0 · Ready 14")
    assert card._summary_values["rows"].text() == "8"
    assert card._summary_values["pending"].text() == "1"
    assert card._summary_values["running"].text() == "1"
    assert card._summary_values["failed"].text() == "0"
    assert card._summary_values["ready"].text() == "14"
    assert not card._summary_counts.isHidden()
    card.set_queue_summary("No batches found in the selected date range.")
    assert card._summary_counts.isHidden()
    assert "No batches found" in card._summary_message.text()

    running = ImageJobListItem(
        id="bg-run", kind="background", channel_role="secondary", status="running"
    )
    waiting = ImageJobListItem(
        id="th-wait", kind="thumbnail", channel_role="secondary", status="pending"
    )
    card.set_rows(
        [
            QueueRow(
                key="row-1",
                batch_id="batch-1",
                song_id="song-1",
                album_label="Shoreline Solitude Stories",
                track_count=2,
                date_label="2026-08-10",
                profile_name="EDM Bass Booster",
                role="secondary",
                bg_job=running,
                th_job=waiting,
                bg_jobs=(running,),
                th_jobs=(waiting,),
            )
        ],
        "row-1",
    )
    assert card._queue_count.isHidden()
    assert card._table.wordWrap() is False
    assert card._table.columnWidth(_COL_ROLE) == 96
    assert card._table.item(0, _COL_ROLE).text() == "Secondary"
    assert card._table.rowHeight(0) == _QUEUE_ROW_HEIGHT
    assert card._table.item(0, 4).background().style() == Qt.BrushStyle.NoBrush
    assert card._selected_album.text() == "Shoreline Solitude Stories"
    assert "EDM Bass Booster" in card._selected_meta.text()
    assert card._queue_count.text() == "1"


def test_selected_album_clears_and_clear_filters_resets_dates(qapp: QApplication) -> None:
    card = ControlsQueueCard()
    card.show()
    card.set_date_range("2026-08-01", "2026-08-10")
    card.clear_filters()
    from shared.lib.formatting import today_ymd

    assert card.from_date() == today_ymd()
    assert card.to_date() == today_ymd()
    assert "Clear Filters" in {button.text() for button in card.findChildren(QPushButton)}
    card.clear_selection()
    assert card._selected_album.text() == "No album selected"
