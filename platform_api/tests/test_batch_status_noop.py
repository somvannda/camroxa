"""Batch status writes must not heartbeat updated_at on no-op refreshes."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.repositories.batch_repo import BatchRepository


@pytest.mark.asyncio
async def test_update_batch_status_skips_when_status_unchanged() -> None:
    pool = AsyncMock()
    repo = BatchRepository(pool)
    batch_id = uuid4()
    await repo.update_batch_status(batch_id, "completed")
    sql = pool.execute.await_args.args[0]
    assert "IS DISTINCT FROM" in sql
    assert pool.execute.await_args.args[1] == batch_id
    assert pool.execute.await_args.args[2] == "completed"
