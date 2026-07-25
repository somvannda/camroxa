"""Tests for History metadata rewrite API client wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from features.music.widgets.history_card import HistoryCard
from shared.models.platform import AlbumRewriteResponse, TitleRewriteResponse
from shared.services.platform_api import PlatformApi


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_history_rewrite_signals_exist(qapp: QApplication) -> None:
    del qapp
    card = HistoryCard()
    assert hasattr(card, "rewrite_album_requested")
    assert hasattr(card, "rewrite_title_requested")


def test_album_and_title_rewrite_response_models() -> None:
    album = AlbumRewriteResponse(batch_id="b1", role="ok", album="Neon Coastal Midnight")
    assert album.album.startswith("Neon")
    title = TitleRewriteResponse(batch_id="b1", song_id="s1", title="Neon Glow Phantom")
    assert title.title.startswith("Neon")


def test_platform_api_rewrite_methods_call_endpoints() -> None:
    client = MagicMock()
    client.request.return_value = {
        "batch_id": "b1",
        "role": "alt",
        "album": "Stories From Glass",
    }
    api = PlatformApi.__new__(PlatformApi)
    api._client = client
    result = api.rewrite_batch_album("b1", role="alt")
    assert result.album == "Stories From Glass"
    client.request.assert_called_with(
        "/batches/b1/rewrite-album",
        method="POST",
        auth=True,
        body={"role": "alt"},
    )

    client.request.return_value = {
        "batch_id": "b1",
        "song_id": "s1",
        "title": "Fresh Title",
    }
    title = api.rewrite_song_title("b1", "s1")
    assert title.title == "Fresh Title"
    client.request.assert_called_with(
        "/batches/b1/songs/s1/rewrite-title",
        method="POST",
        auth=True,
    )
