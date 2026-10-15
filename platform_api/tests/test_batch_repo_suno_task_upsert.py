"""Suno task persistence must not collide with a stale *failed* row (issue #372).

``suno_tasks`` is ``UNIQUE(user_id, request_hash)`` while ``find_by_hash`` skips
failed rows so a retry regenerates. A plain INSERT therefore raised
``duplicate key value violates unique constraint "suno_tasks_user_id_request_hash_key"``
on every retry, which the batch path surfaced as a ``v3_music`` charge followed
immediately by a ``suno_generation_failed`` refund. ``create_suno_task`` is an
upsert that revives the failed row instead.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from platform_api.models.domain import SunoTask, TaskStatus
from platform_api.repositories.batch_repo import BatchRepository


class _RecordingPool:
    def __init__(self, fetchval_results: list[Any]) -> None:
        self.queries: list[str] = []
        self._results = list(fetchval_results)

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.queries.append(" ".join(query.split()))
        if self._results:
            return self._results.pop(0)
        return None


def _task(user_id: UUID, request_hash: str = "hash-abc") -> SunoTask:
    return SunoTask(
        id=uuid4(),
        user_id=user_id,
        request_hash=request_hash,
        model="V6",
        title="Moonlit Harbor Solitude",
        lyrics="la la",
        style="pop",
        status=TaskStatus.PENDING,
    )


async def test_create_suno_task_revives_a_failed_row() -> None:
    """A conflict on the failed row returns that row's id and resets it."""
    user_id = uuid4()
    existing_id = uuid4()
    pool = _RecordingPool([existing_id])
    repo = BatchRepository(pool)  # type: ignore[arg-type]

    task = _task(user_id)
    result = await repo.create_suno_task(task)

    assert result.id == existing_id  # reused, not a new row
    query = pool.queries[0]
    assert "ON CONFLICT (user_id, request_hash) DO UPDATE" in query
    assert "WHERE suno_tasks.status = 'failed'" in query
    assert "RETURNING id" in query
    # A regenerated attempt must not carry the previous failure/audio.
    assert "error_message = NULL" in query
    assert "downloaded_ok = false" in query


async def test_create_suno_task_fresh_insert_keeps_new_id() -> None:
    user_id = uuid4()
    task = _task(user_id)
    pool = _RecordingPool([task.id])
    repo = BatchRepository(pool)  # type: ignore[arg-type]

    result = await repo.create_suno_task(task)

    assert result.id == task.id


async def test_create_suno_task_live_conflict_keeps_existing_row() -> None:
    """A conflict with a live/successful task is never clobbered."""
    user_id = uuid4()
    existing_id = uuid4()
    # INSERT ... DO UPDATE ... WHERE status='failed' matches nothing -> NULL,
    # then the fallback SELECT returns the live row's id.
    pool = _RecordingPool([None, existing_id])
    repo = BatchRepository(pool)  # type: ignore[arg-type]

    task = _task(user_id)
    result = await repo.create_suno_task(task)

    assert result.id == existing_id
    assert len(pool.queries) == 2
    assert "SELECT id FROM suno_tasks" in pool.queries[1]
    assert "status = 'failed'" not in pool.queries[1]
