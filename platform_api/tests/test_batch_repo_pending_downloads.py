"""Pending-download ordering must keep each pipeline's tracks contiguous."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from platform_api.repositories.batch_repo import BatchRepository


class _RecordingPool:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.queries.append(query)
        return []


async def test_pending_downloads_are_grouped_by_pipeline() -> None:
    pool = _RecordingPool()
    repo = BatchRepository(pool)  # type: ignore[arg-type]

    await repo.list_pending_suno_downloads(user_id=uuid4(), limit=24)

    assert len(pool.queries) == 1
    query = " ".join(pool.queries[0].split())
    # Batches ordered by recency, then every track of a batch kept together so the
    # client finishes one pipeline before starting the next.
    assert "ORDER BY COALESCE(b.updated_at, st.updated_at) DESC" in query
    assert "st.batch_id," in query
    assert "s.batch_index ASC NULLS LAST" in query
