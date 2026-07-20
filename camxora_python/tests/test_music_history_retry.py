from shared.models.platform import MusicHistoryBatch, MusicHistoryListResponse, MusicHistorySong
from features.music.lib.history_retry import history_track_number


def test_history_track_number_from_batches():
    history = MusicHistoryListResponse(
        batches=[
            MusicHistoryBatch(
                batch_id="b1",
                songs=[
                    MusicHistorySong(song_id="s0", batch_index=0),
                    MusicHistorySong(song_id="s1", batch_index=1),
                ],
            )
        ]
    )
    assert history_track_number(history, "s1") == 2
    assert history_track_number(history, "missing") is None
