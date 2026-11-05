"""A schema mismatch must show up on /health, not only in a log line.

Production sat at `alembic_version = 178` with
`credit_transactions.reason` still `varchar(100)` while `/health` reported
"healthy"; the CRITICAL log line existed and nobody was looking for it. The
runner now records the assertion result and `/health` reports it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from platform_api.migrations import runner
from platform_api.services import schema_status


@pytest.fixture(autouse=True)
def _clean_status() -> None:
    schema_status.reset()
    yield
    schema_status.reset()


def test_status_starts_unchecked() -> None:
    assert schema_status.snapshot() == {"checked": False, "ok": True, "failures": []}


def test_status_records_failures() -> None:
    schema_status.record(["credit_transactions.reason: 'character varying'"])

    snapshot = schema_status.snapshot()
    assert snapshot["checked"] is True
    assert snapshot["ok"] is False
    assert snapshot["failures"] == ["credit_transactions.reason: 'character varying'"]


def test_reset_clears_the_record() -> None:
    schema_status.record(["boom"])
    schema_status.reset()

    assert schema_status.snapshot()["checked"] is False
    assert schema_status.snapshot()["ok"] is True


@pytest.mark.asyncio
async def test_runner_records_a_passing_pass() -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["text", "1"])

    failures = await runner.verify_schema_assertions(conn)

    assert failures == []
    assert schema_status.snapshot()["checked"] is True
    assert schema_status.snapshot()["ok"] is True


@pytest.mark.asyncio
async def test_runner_records_the_production_failure() -> None:
    """The exact state that hid for days: version ahead, column still varchar."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["character varying", "1"])

    failures = await runner.verify_schema_assertions(conn)

    assert len(failures) == 1
    snapshot = schema_status.snapshot()
    assert snapshot["checked"] is True
    assert snapshot["ok"] is False
    assert "character varying" in snapshot["failures"][0]


@pytest.mark.asyncio
async def test_runner_flags_a_lot_constraint_without_admin() -> None:
    """A table rebuild that restores an older tag CHECK breaks admin comps."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["text", "0"])

    failures = await runner.verify_schema_assertions(conn)

    assert len(failures) == 1
    assert "credit_wallet_lots.tag accepts admin" in failures[0]
    assert schema_status.snapshot()["ok"] is False
