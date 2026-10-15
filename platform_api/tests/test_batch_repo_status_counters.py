"""Batch status counters must be per song, not per Suno task row.

A song can have several ``suno_tasks`` rows (superseded failures, retries). If the
counters counted rows, a batch whose songs are all ``suno_success`` would stay
``partial`` forever because of a stale failed row or a duplicate success row.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from platform_api.repositories.batch_repo import BatchRepository


class _Pool:
    def __init__(self, song_rows: list[dict[str, Any]], fetchvals: list[Any]) -> None:
        self._song_rows = song_rows
        self._fetchvals = list(fetchvals)
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.queries.append(" ".join(query.split()))
        return self._song_rows

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.queries.append(" ".join(query.split()))
        return self._fetchvals.pop(0) if self._fetchvals else 0


async def test_counters_use_song_terminal_state_not_task_rows() -> None:
    # 15 songs, all suno_success; the stale failed/duplicate task rows are NOT
    # represented here because the repository no longer counts them.
    pool = _Pool(
        song_rows=[{"status": "suno_success", "cnt": 15}],
        fetchvals=[15, 15, 0],  # distinct task songs, downloaded, images
    )
    repo = BatchRepository(pool)  # type: ignore[arg-type]

    counters = await repo.get_batch_status_counters(uuid4())

    assert counters["total_songs"] == 15
    assert counters["drafts_completed"] == 15
    assert counters["suno_completed"] == 15
    assert counters["suno_failed"] == 0
    assert counters["suno_submitted"] == 15
    # The per-song submission count must be a DISTINCT song count, not a row count.
    suno_query = next(q for q in pool.queries if "suno_tasks" in q)
    assert "COUNT(DISTINCT song_id)" in suno_query
    # No per-status task aggregation remains.
    assert not any("GROUP BY status" in q and "suno_tasks" in q for q in pool.queries)


async def test_counters_report_failed_songs_per_song() -> None:
    pool = _Pool(
        song_rows=[
            {"status": "suno_success", "cnt": 14},
            {"status": "suno_failed", "cnt": 1},
        ],
        fetchvals=[15, 14, 0],
    )
    repo = BatchRepository(pool)  # type: ignore[arg-type]

    counters = await repo.get_batch_status_counters(uuid4())

    assert counters["suno_completed"] == 14
    assert counters["suno_failed"] == 1
