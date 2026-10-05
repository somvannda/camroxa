"""Tests for the startup migration runner's cross-worker coordination."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform_api.migrations import runner


GRAPH = {
    "083": "082",
    "084_user_products_web_music": "083",
    "084_provider_balance_events": "083",
    "104_suno_task_durations": "084_user_products_web_music",
}


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
    lock_conn.fetch = AsyncMock(return_value=[{"version_num": "104_suno_task_durations"}])

    with (
        patch("platform_api.migrations.runner.asyncpg.connect", AsyncMock(return_value=lock_conn)),
        patch("platform_api.migrations.runner._upgrade_head_sync") as upgrade_mock,
        patch("platform_api.migrations.runner.get_settings") as settings_mock,
    ):
        settings_mock.return_value = MagicMock(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/db"
        )
        await runner.run_pending_migrations()

    upgrade_mock.assert_called_once_with({"104_suno_task_durations"})
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
    lock_conn.fetch = AsyncMock(return_value=[])

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


@pytest.mark.asyncio
async def test_run_pending_migrations_times_out_stuck_upgrade() -> None:
    lock_conn = AsyncMock()
    lock_conn.fetch = AsyncMock(return_value=[])

    async def _timeout(awaitable: object, timeout: object) -> None:
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise TimeoutError

    with (
        patch("platform_api.migrations.runner.asyncpg.connect", AsyncMock(return_value=lock_conn)),
        patch("platform_api.migrations.runner.asyncio.wait_for", _timeout),
        patch("platform_api.migrations.runner.get_settings") as settings_mock,
    ):
        settings_mock.return_value = MagicMock(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/db"
        )
        with pytest.raises(RuntimeError, match="exceeded"):
            await runner.run_pending_migrations()

    unlock_calls = [
        c for c in lock_conn.execute.call_args_list if "pg_advisory_unlock" in c.args[0]
    ]
    # On timeout the lock must stay held (the stuck upgrade thread is still
    # running); releasing it here could allow a concurrent upgrade.
    assert len(unlock_calls) == 0
    lock_conn.close.assert_not_awaited()


def test_leftover_sibling_084_is_skipped_when_current_is_on_other_branch() -> None:
    leftover = runner.leftover_fork_revisions(GRAPH, {"104_suno_task_durations"})
    assert leftover == {"084_provider_balance_events"}
    target = runner.upgrade_revision_target(
        GRAPH,
        ["084_provider_balance_events", "104_suno_task_durations"],
        {"104_suno_task_durations"},
    )
    assert target == "104_suno_task_durations"


def test_linear_graph_has_no_leftover_forks() -> None:
    linear = {
        "083": "082",
        "084_user_products_web_music": "083",
        "104_suno_task_durations": "084_user_products_web_music",
    }
    assert runner.leftover_fork_revisions(linear, {"104_suno_task_durations"}) == set()
    assert (
        runner.upgrade_revision_target(
            linear,
            ["104_suno_task_durations"],
            {"104_suno_task_durations"},
        )
        == "104_suno_task_durations"
    )


def test_unapplied_fork_is_not_leftover_on_fresh_database() -> None:
    assert runner.leftover_fork_revisions(GRAPH, set()) == set()
    assert (
        runner.upgrade_revision_target(
            GRAPH,
            ["084_provider_balance_events", "104_suno_task_durations"],
            set(),
        )
        == "heads"
    )


def test_merge_revision_is_not_treated_as_a_sibling_fork() -> None:
    graph = {
        "083": None,
        "084_a": "083",
        "091": "083",
        "103_merge": ("084_a", "091"),
    }
    assert runner.leftover_fork_revisions(graph, {"103_merge"}) == set()


def test_upgrade_head_sync_skips_when_db_revision_missing_locally() -> None:
    """DB ahead of this checkout must not try to downgrade to an older local head."""
    script = MagicMock()
    script.walk_revisions.return_value = [
        MagicMock(revision="116_credits_only_v3", down_revision="115_hls_playback"),
    ]
    script.get_heads.return_value = ["116_credits_only_v3"]
    alembic_ini = MagicMock()
    alembic_ini.is_file.return_value = True
    platform_root = MagicMock()
    platform_root.__truediv__.return_value = alembic_ini

    with (
        patch("platform_api.migrations.runner.Path") as path_cls,
        patch("platform_api.migrations.runner.Config"),
        patch("platform_api.migrations.runner.ScriptDirectory.from_config", return_value=script),
        patch("platform_api.migrations.runner.command.upgrade") as upgrade_mock,
        patch("platform_api.migrations.runner.get_settings") as settings_mock,
    ):
        path_cls.return_value.resolve.return_value.parents = [None, platform_root]
        settings_mock.return_value = MagicMock(database_url="postgresql+asyncpg://u:p@localhost/db")
        runner._upgrade_head_sync({"117_daily_grant_lot_tag"})

    upgrade_mock.assert_not_called()
