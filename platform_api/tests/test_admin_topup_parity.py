"""Admin comps must obey the same wallet rules as a pack credit.

``CreditService.admin_adjust`` already mints an ``admin`` lot stamped 30 days out
-- the lot ledger and the wallet move in one transaction -- but two places only
knew about ``pack``:

* ``expired_lots()`` swept grant/daily_grant/pack/referral, so an admin lot was
  the only wallet credit that never burned.
* ``has_paid_desktop_access()`` required ``tag = 'pack'``, so a comped user got a
  spendable balance the studio gate rejected.

The paid-month probes (``has_completed_topup_this_month`` and the Telegram ops
snapshot) also read ``topup_purchases`` only, which a comp never writes, so a
comped Free user dropped back to V6-Mini and was badged FREE.

Everything else stays purchase-only on purpose: revenue, receipts, refunds and
the referral reward. No synthetic ``topup_purchases`` row is created, and the
legacy ``topup_credits_balance`` decrement is **not** mirrored -- it reverses the
``091`` trigger, which a comp never fires, so copying it would confiscate legacy
credits.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from platform_api.repositories.license_repo import LicenseRepository
from platform_api.services.v3.store import V3BillingStore

USER_ID = uuid4()


class _RecordingPool:
    def __init__(self, *, fetchval_result: Any = None) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchval_result = fetchval_result

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        self.calls.append((sql, args))
        return []

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.calls.append((sql, args))
        return self._fetchval_result


@pytest.mark.asyncio
async def test_expiry_sweep_covers_admin_lots() -> None:
    """A comp must burn at its 30-day date like a pack."""
    pool = _RecordingPool()
    store = V3BillingStore(pool)

    await store.expired_lots(USER_ID)

    sql, args = pool.calls[0]
    assert args == (USER_ID,)
    assert "'admin'" in sql
    assert "'pack'" in sql


@pytest.mark.asyncio
async def test_desktop_gate_accepts_admin_lots() -> None:
    """A comped user can open the studio while the credit is live."""
    pool = _RecordingPool(fetchval_result=True)
    repo = LicenseRepository(pool=pool)

    assert await repo.has_paid_desktop_access(str(USER_ID)) is True

    sql, _args = pool.calls[0]
    assert "lot.tag IN ('pack', 'admin')" in sql
    assert "expires_at > NOW()" in sql
    assert "balance FROM credit_wallets" in sql


@pytest.mark.asyncio
async def test_paid_month_probe_counts_admin_topups() -> None:
    """The premium-unlock probe must treat a comp like a purchase."""
    pool = _RecordingPool(fetchval_result=None)
    store = V3BillingStore(pool)

    await store.has_completed_topup_this_month(USER_ID)

    sql, _args = pool.calls[0]
    # Purchases still count exactly as before, refunds included.
    assert "payment_status = 'completed'" in sql
    # An admin top-up counts as paid-tier credit for the month.
    assert "admin_adjustment:" in sql
    # Only granted credit counts -- a clawback must never unlock the month.
    assert "direction = 'credit'" in sql
    assert "amount > 0" in sql


def test_admin_adjust_mints_its_lot_and_no_purchase_row() -> None:
    """Guard the deliberate asymmetry: a comp is a lot, never a sale."""
    import inspect

    from platform_api.services import credit_service

    source = inspect.getsource(credit_service.CreditService.admin_adjust)
    # The lot is minted by the same add_credits call as the balance.
    assert "create_lot=True" in source
    assert 'lot_tag="admin"' in source
    assert "timedelta(days=30)" in source
    # ...and nothing pretends it was a purchase.
    assert "topup_purchases" not in source
    assert "subtract_web_topup" not in source
