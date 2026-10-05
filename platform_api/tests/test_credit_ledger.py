"""CreditLedger facade: typed grant/deduct/refund delegation."""

from __future__ import annotations

from uuid import uuid4

from platform_api.services.credit_ledger import CreditLedger, GrantType


class _Repo:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def add_credits(
        self,
        user_id,
        amount,
        reason,
        ref_id=None,
        pack_id=None,
        payment_ref=None,
        *,
        metadata=None,
        idempotent=True,
    ) -> int:
        self.calls.append(
            {
                "op": "grant",
                "amount": amount,
                "reason": reason,
                "ref_id": ref_id,
                "metadata": metadata,
                "idempotent": idempotent,
            }
        )
        return amount

    async def atomic_deduct(self, user_id, amount, reason, ref_id=None, metadata=None) -> bool:
        self.calls.append({"op": "deduct", "amount": amount, "reason": reason, "ref_id": ref_id})
        return True

    async def refund(self, user_id, amount, reason, ref_id=None, metadata=None) -> int:
        self.calls.append({"op": "refund", "amount": amount, "reason": reason, "ref_id": ref_id})
        return amount


async def test_grant_uses_enum_reason() -> None:
    repo = _Repo()
    await CreditLedger(repo).grant(
        uuid4(), 500, grant_type=GrantType.PERIOD, ref_id="grant:u:2026-10-01"
    )
    assert repo.calls[0]["reason"] == "v3_period_grant"
    assert repo.calls[0]["idempotent"] is True


async def test_grant_accepts_plain_string_reason() -> None:
    repo = _Repo()
    await CreditLedger(repo).grant(uuid4(), 100, grant_type="admin adjustment: test", ref_id="x")
    assert repo.calls[0]["reason"] == "admin adjustment: test"


async def test_grant_idempotent_false_passthrough() -> None:
    repo = _Repo()
    await CreditLedger(repo).grant(
        uuid4(), 100, grant_type=GrantType.REDEEM, ref_id="code-1", idempotent=False
    )
    assert repo.calls[0]["idempotent"] is False


async def test_deduct_and_refund_delegate() -> None:
    repo = _Repo()
    ledger = CreditLedger(repo)
    assert await ledger.deduct(uuid4(), 10, reason="v3_music", ref_id="t") is True
    await ledger.refund(uuid4(), 10, reason="v3_refund_music", ref_id="d")
    ops = [call["op"] for call in repo.calls]
    assert ops == ["deduct", "refund"]
