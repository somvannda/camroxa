"""Tests for the startup migration runner's cross-worker coordination."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform_api.migrations import runner


@pytest.mark.asyncio
async def test_run_pending_migrations_acquires_and_releases_advisory_lock() -> None:
    """The advisory lock must be acquired before upgrading and released after,
    even though the actual `alembic upgrade heads` call runs in a worker thread.
    """
    lock_conn = AsyncMock()
    calls: list[str] = []

    async def _execute(sql: str, *args: object) -> None:
        calls.append(sql)

    lock_conn.execute.side_effect = _execute

    with (
        patch("platform_api.migrations.runner.asyncpg.connect", AsyncMock(return_value=lock_conn)),
        patch("platform_api.migrations.runner._upgrade_head_sync") as upgrade_mock,
        patch("platform_api.migrations.runner.get_settings") as settings_mock,
    ):
        settings_mock.return_value = MagicMock(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/db"
        )
        await runner.run_pending_migrations()

    upgrade_mock.assert_called_once()
    assert any("pg_advisory_lock" in c for c in calls)
    assert any("pg_advisory_unlock" in c for c in calls)
    # Lock must be acquired strictly before unlock in call order.
    lock_index = next(i for i, c in enumerate(calls) if "pg_advisory_lock" in c and "unlock" not in c)
    unlock_index = next(i for i, c in enumerate(calls) if "pg_advisory_unlock" in c)
    assert lock_index < unlock_index
    lock_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_pending_migrations_releases_lock_even_if_upgrade_fails() -> None:
    """A failed upgrade must not leave the advisory lock held forever."""
    lock_conn = AsyncMock()

    with (
        patch("platform_api.migrations.runner.asyncpg.connect", AsyncMock(return_value=lock_conn)),
        patch(
            "platform_api.migrations.runner._upgrade_head_sync",
            side_effect=RuntimeError("boom"),
        ),
        patch("platform_api.migrations.runner.get_settings") as settings_mock,
    ):
        settings_mock.return_value = MagicMock(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/db"
        )
        with pytest.raises(RuntimeError):
            await runner.run_pending_migrations()

    unlock_calls = [
        c for c in lock_conn.execute.call_args_list if "pg_advisory_unlock" in c.args[0]
    ]
    assert len(unlock_calls) == 1
    lock_conn.close.assert_awaited_once()
