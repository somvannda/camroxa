"""History card filter defaults and row rendering."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.music.widgets.history_card import HistoryCard, HistoryRow, batch_retry_targets
from shared.lib.formatting import today_ymd
from shared.models.platform import MusicHistoryBatch, MusicHistorySong


def _song(
    song_id: str,
    batch_index: int,
    *,
    title: str | None = "Pending title",
    status: str = "pending",
    suno_status: str | None = None,
) -> MusicHistorySong:
    return MusicHistorySong(
        song_id=song_id,
        batch_index=batch_index,
        title=title,
        description_name="Dark Phonk Trap",
        structure_name="Dark Atmospheric",
        status=status,
        suno_status=suno_status,
    )


def _batch(batch_id: str, *, song_count: int = 1) -> MusicHistoryBatch:
    return MusicHistoryBatch(
        batch_id=batch_id,
        song_count=song_count,
        ok_profile_name="Bass Drive",
        alt_profile_name="Beattok Remixes",
        from_date="2026-07-11",
        created_at="2026-07-11T19:09:00",
        songs=[_song(f"{batch_id}-song-{index}", index) for index in range(song_count)],
    )


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_history_filters_default_to_today(qapp: QApplication) -> None:
    card = HistoryCard()
    values = card.filter_values()
    today = today_ymd()
    assert values["from_date"] == today
    assert values["to_date"] == today
    assert values["last_batch_only"] is False


def test_show_all_clears_date_filter(qapp: QApplication) -> None:
    card = HistoryCard()
    card._clear_filters()
    values = card.filter_values()
    assert values["from_date"] == ""
    assert values["to_date"] == ""


def test_set_rows_clears_stale_separator_widgets(qapp: QApplication) -> None:
    card = HistoryCard()
    first_batch = _batch("fdfcbde8-0000-0000-0000-000000000001", song_count=5)
    second_batch = _batch("38e00000-0000-0000-0000-000000000002", song_count=1)

    card.set_rows(
        [
            HistoryRow(batch=first_batch, is_batch_separator=True),
            *[HistoryRow(row_number=index + 1, batch=first_batch, song=song) for index, song in enumerate(first_batch.songs)],
            HistoryRow(batch=second_batch, is_batch_separator=True),
            HistoryRow(row_number=6, batch=second_batch, song=second_batch.songs[0]),
        ],
        selected_song_id=None,
    )

    card.set_rows(
        [
            HistoryRow(batch=first_batch, is_batch_separator=True),
            *[HistoryRow(row_number=index + 1, batch=first_batch, song=song) for index, song in enumerate(first_batch.songs)],
        ],
        selected_song_id=None,
    )

    last_song_row = card._table.rowCount() - 1
    assert card._table.cellWidget(last_song_row, 0) is None
    assert card._table.item(last_song_row, 0).text() == "5"


def test_title_cell_switches_from_generating_widget_to_text(qapp: QApplication) -> None:
    card = HistoryCard()
    batch = _batch("1a66aad5-0000-0000-0000-000000000001", song_count=1)
    pending_song = _song(f"{batch.batch_id}-song-0", 0, title=None, status="pending")
    ready_song = _song(
        f"{batch.batch_id}-song-0",
        0,
        title="Northern Avenue Codes",
        status="draft_ready",
    )

    card.set_rows(
        [
            HistoryRow(batch=batch, is_batch_separator=True),
            HistoryRow(row_number=1, batch=batch, song=pending_song),
        ],
        selected_song_id=None,
    )
    assert card._table.cellWidget(1, 3) is not None
    assert card._table.item(1, 3) is None

    card.set_rows(
        [
            HistoryRow(batch=batch, is_batch_separator=True),
            HistoryRow(row_number=1, batch=batch, song=ready_song),
        ],
        selected_song_id=None,
    )
    assert card._table.cellWidget(1, 3) is None
    title_item = card._table.item(1, 3)
    assert title_item is not None
    assert title_item.text() == "Northern Avenue Codes"
    assert "#" not in title_item.text()


def test_history_album_columns_use_album_1_album_2(qapp: QApplication) -> None:
    card = HistoryCard()
    batch = _batch("a1000000-0000-0000-0000-000000000001", song_count=1)
    batch = batch.model_copy(
        update={
            "ok_album": "Midnight Drive",
            "alt_album": "Sunset Pulse",
            "songs": [
                batch.songs[0].model_copy(update={"album": "Midnight Drive"}),
            ],
        }
    )
    card.set_rows(
        [
            HistoryRow(batch=batch, is_batch_separator=True),
            HistoryRow(row_number=1, batch=batch, song=batch.songs[0]),
        ],
        selected_song_id=None,
    )
    headers = [
        card._table.horizontalHeaderItem(index).text()
        for index in range(card._table.columnCount())
    ]
    assert headers[1] == "album 1"
    assert headers[2] == "album 2"
    assert card._table.item(1, 1).text() == "Midnight Drive"
    assert card._table.item(1, 2).text() == "Sunset Pulse"
    assert "album 1 Midnight Drive" in card._table.item(0, 0).text()
    assert "album 2 Sunset Pulse" in card._table.item(0, 0).text()


def test_song_rows_use_compact_fixed_height(qapp: QApplication) -> None:
    card = HistoryCard()
    batch = _batch("d234eec2-0000-0000-0000-000000000001", song_count=2)

    card.set_rows(
        [
            HistoryRow(batch=batch, is_batch_separator=True),
            HistoryRow(row_number=1, batch=batch, song=batch.songs[0]),
            HistoryRow(row_number=2, batch=batch, song=batch.songs[1]),
        ],
        selected_song_id=None,
    )

    assert card._table.rowHeight(0) == 26
    assert card._table.rowHeight(1) == 36
    assert card._table.rowHeight(2) == 36


def test_batch_retry_targets_collects_failed_songs_only(qapp: QApplication) -> None:
    batch = MusicHistoryBatch(
        batch_id="batch-1",
        song_count=4,
        songs=[
            _song("s1", 0, status="draft_failed"),
            _song("s2", 1, status="pending"),
            _song("s3", 2, status="draft_ready", suno_status="suno_failed"),
            _song("s4", 3, status="suno_failed"),
        ],
    )
    draft_ids, suno_ids = batch_retry_targets(batch)
    assert draft_ids == ["s1"]
    assert suno_ids == ["s3", "s4"]
