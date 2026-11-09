"""Admin adjust reasons must fit the ledger column they land in.

``credit_transactions.reason`` was ``VARCHAR(100)`` while the admin route accepts
255 characters and stores them prefixed with ``admin_adjustment: ``. A long
reason therefore failed the insert *after* the balance check, so the operator saw
a 500 and nothing applied. Migration 178 widens the column to ``TEXT``.

These tests pin both halves of that contract: the route accepts the long reason,
and the migration that lets it persist keeps widening the column.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from platform_api.routers.credits import AdjustBalanceRequest

LONG_REASON = "c" * 255


class _RecordingOp:
    def __init__(self) -> None:
        self.sql: list[str] = []

    def execute(self, sql: str) -> None:
        self.sql.append(sql)


def _load_migration() -> Any:
    return importlib.import_module(
        "platform_api.migrations.versions.178_credit_txn_reason_text"
    )


def test_admin_reason_may_exceed_the_old_column_width() -> None:
    """255 chars + the ``admin_adjustment: `` prefix is why the column moved."""
    request = AdjustBalanceRequest(
        user_id="9eebdf0a-d9b3-487f-b4ec-fbfab6f17a80",
        amount=10,
        reason=LONG_REASON,
    )
    assert len(f"admin_adjustment: {request.reason}") > 100
    assert len(request.reason) == 255


def test_reason_field_still_rejects_an_unbounded_reason() -> None:
    with pytest.raises(ValueError):
        AdjustBalanceRequest(
            user_id="9eebdf0a-d9b3-487f-b4ec-fbfab6f17a80",
            amount=10,
            reason="c" * 256,
        )


def test_migration_178_widens_reason_to_text(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_migration()
    assert module.revision == "178"
    assert module.down_revision == "177"

    op = _RecordingOp()
    monkeypatch.setattr(module, "op", op)
    module.upgrade()

    assert len(op.sql) == 1
    sql = op.sql[0]
    assert "ALTER TABLE credit_transactions" in sql
    assert "ALTER COLUMN reason TYPE TEXT" in sql


def test_migration_178_downgrade_truncates_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration()
    op = _RecordingOp()
    monkeypatch.setattr(module, "op", op)
    module.downgrade()

    assert len(op.sql) == 1
    assert "VARCHAR(100) USING left(reason, 100)" in op.sql[0]
