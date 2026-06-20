"""Credit service protocol interface.

Defines the contract for credit wallet operations including balance queries,
atomic deductions, refunds, and credit pack purchases.
"""

from __future__ import annotations

from typing import Protocol


class CreditServicePort(Protocol):
    """Port for credit wallet management.

    Implementations handle atomic credit deductions, refunds, balance queries,
    and credit pack purchases with overflow protection.
    """

    async def get_balance(self, user_id: str) -> int:
        """Return the current credit wallet balance for a user.

        Returns a non-negative integer representing available credits.
        """
        ...

    async def deduct(self, user_id: str, amount: int, reason: str, ref_id: str) -> bool:
        """Atomically deduct credits from a user's wallet.

        Returns True if the deduction succeeded (sufficient balance).
        Returns False if the balance is insufficient (no partial deduction).
        The operation is atomic: concurrent requests cannot overdraw below zero.
        """
        ...

    async def refund(self, user_id: str, amount: int, reason: str, ref_id: str) -> None:
        """Refund credits to a user's wallet.

        Used when an external service call fails after credits were deducted.
        Records a refund transaction for audit purposes.
        """
        ...

    async def purchase_pack(self, user_id: str, pack_id: str, payment_ref: str) -> int:
        """Purchase a credit pack and add credits to the user's wallet.

        Returns the new wallet balance after the purchase.
        Raises an error if the purchase would exceed the maximum wallet balance
        (10,000,000 credits).
        """
        ...
