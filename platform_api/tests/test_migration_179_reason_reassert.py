"""A recorded revision is not proof its DDL landed.

Production reached ``alembic_version = 178`` with
``credit_transactions.reason`` still ``character varying(100)``: ``174`` rebuilds
tables from ``*_archive`` snapshots and that deploy also reported
``DEPLOY_LOCK_NOT_OWNER``, so a concurrent runner most likely restored the
pre-178 shape after the ALTER.

Migration ``179`` re-asserts the type. These tests pin both halves: the migration
that fixes it, and the startup assertion that makes the next silent mismatch
impossible to miss.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock

import pytest

from platform_api.migrations import runner


class _FakeConn:
    def __init__(self, value: Any = None, error: Exception | None = None) -> None:
        self._value = value
        self._error = error
        self.fetchval = AsyncMock(side_effect=self._fetchval)

    async def _fetchval(self, *_args: Any, **_kwargs: Any) -> Any:
        if self._error is not None:
            raise self._error
        return self._value


def _load_migration() -> Any:
    return importlib.import_module(
        "platform_api.migrations.versions.179_credit_txn_reason_text_reassert"
    )


def test_migration_179_follows_178_and_reasserts_text(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_migration()
    assert module.revision == "179"
    assert module.down_revision == "178"

    executed: list[str] = []
    monkeypatch.setattr(
        module, "op", type("_Op", (), {"execute": staticmethod(executed.append)})
    )
    module.upgrade()

    assert len(executed) == 1
    assert "ALTER TABLE credit_transactions" in executed[0]
    assert "ALTER COLUMN reason TYPE TEXT" in executed[0]


def test_migration_179_downgrade_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    """Narrowing back would truncate real admin reasons."""
    module = _load_migration()
    executed: list[str] = []
    monkeypatch.setattr(
        module, "op", type("_Op", (), {"execute": staticmethod(executed.append)})
    )
    module.downgrade()

    assert executed == []


@pytest.mark.asyncio
async def test_schema_assertion_passes_when_column_is_text() -> None:
    conn = _FakeConn(value="text")

    failures = await runner.verify_schema_assertions(conn)  # type: ignore[arg-type]

    assert failures == []


@pytest.mark.asyncio
async def test_schema_assertion_reports_the_wrong_type() -> None:
    """The exact production state: version ahead, column still varchar."""
    conn = _FakeConn(value="character varying")

    failures = await runner.verify_schema_assertions(conn)  # type: ignore[arg-type]

    assert len(failures) == 1
    assert "credit_transactions.reason" in failures[0]
    assert "character varying" in failures[0]


@pytest.mark.asyncio
async def test_schema_assertion_never_raises_on_query_error() -> None:
    conn = _FakeConn(error=RuntimeError("relation does not exist"))

    failures = await runner.verify_schema_assertions(conn)  # type: ignore[arg-type]

    assert failures == ["credit_transactions.reason: <query failed>"]
