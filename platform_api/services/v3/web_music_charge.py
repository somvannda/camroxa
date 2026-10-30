"""Web Create debit when ``credits_only_v3_charge`` is On.

Spec alignment (docs/credits-only-plan-unification.md):
- One charge model: ``amount = plan.<op>_credits``, refund on failure.
- Music is 10 for everyone, including Desktop Pro (no skip).
- Lyrics assist uses ``lyric``; style assist uses ``style``.
- Free daily credits come from the Free plan row via a v3 daily lot.
- One wallet: generate always debits ``credit_wallets``. No v2 fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from platform_api.exceptions import InsufficientCreditsError, QuotaExceededError
from platform_api.services.credit_units import units_to_credits
from platform_api.services.free_monthly_grant import FREE_MONTHLY_CREDITS
from platform_api.services.v3.generate_charge import map_v1_op_to_v3

ChargePath = Literal["v3", "v2", "included"]

# Free-plan users may spend the monthly grant on V6-Mini only until they buy a
# pack in the same calendar month. Suno/model keys arrive as both `V6_MINI`
# (UI) and `V6-MINI` (docs), so normalise separators before matching.
_FREE_MODEL_KEYS = {"V6-MINI", "CHIRP-GOOSE"}


def _model_key(model: str | None) -> str:
    return (
        str(model or "")
        .strip()
        .upper()
        .replace("_", "-")
        .replace(" ", "-")
        .replace(".", "-")
    )


def model_allows_free_grant(
    model: str | None,
    *,
    is_free_plan: bool,
    has_pack_this_month: bool,
) -> bool:
    """Whether a Free-plan user may use this model with the monthly grant."""
    if not is_free_plan:
        return True
    key = _model_key(model)
    if not key or key in _FREE_MODEL_KEYS:
        return True
    return has_pack_this_month


def _premium_label(model: str | None) -> str:
    key = _model_key(model)
    if key in {"V6", "V6-PRO"}:
        return "V6-Pro"
    if key == "V6-WILD":
        return "V6-Wild"
    return str(model or "This model")


@dataclass(slots=True)
class WebMusicCharge:
    path: ChargePath
    op: str
    amount_credits: int
    ref_id: str | None = None


def _upgrade_error(
    message: str,
    *,
    required: int,
    available: int,
) -> QuotaExceededError:
    return QuotaExceededError(
        message,
        details={
            "credits_required": required,
            "credits_available": available,
            "requires_upgrade": True,
        },
    )


class WebMusicChargeBridge:
    def __init__(
        self,
        *,
        v3_billing: Any,
        v3_grant: Any,
        v3_store: Any,
        credit_repo: Any,
        credit_service: Any | None,
        has_paid_web_subscription,
    ) -> None:
        self._billing = v3_billing
        self._grant = v3_grant
        self._store = v3_store
        self._credit_repo = credit_repo
        self._credit_service = credit_service
        self._has_paid_web_subscription = has_paid_web_subscription

    async def quote_credits(self, user_id: UUID, operation: str) -> tuple[str, int, Any]:
        op = map_v1_op_to_v3(operation) or str(operation or "").strip().lower()
        # Plans are retired: the price comes from the `pricing` table alone.
        quote = await self._billing.quote(op=op, user_id=user_id, plan_id=None)
        amount = max(0, int(round(float(quote.amount_credits or 0))))
        return op, amount, quote

    async def charge(
        self,
        user_id: UUID,
        operation: str,
        *,
        ref_id: str | None = None,
        model: str | None = None,
        allow_free_preview: bool = False,
    ) -> WebMusicCharge:
        await self._grant.ensure_daily_grant(user_id)
        await self._grant.ensure_period_grant(user_id)
        op, amount, quote = await self.quote_credits(user_id, operation)
        if amount <= 0 or bool(getattr(quote, "included", False)):
            return WebMusicCharge(path="included", op=op, amount_credits=0, ref_id=ref_id)

        await self._enforce_free_model_scope(
            user_id, model, allow_free_preview=allow_free_preview
        )

        return await self._charge_v3(user_id, op, amount, ref_id=ref_id, model=model)

    async def _enforce_free_model_scope(
        self,
        user_id: UUID,
        model: str | None,
        *,
        allow_free_preview: bool = False,
    ) -> None:
        """Block premium models for Free-plan users until they buy a pack.

        The Free plan's monthly credits are granted into the shared wallet, so
        this is the only place the V6-Mini-only rule can be enforced. A paid
        plan is unrestricted; a completed top-up in the same calendar month
        unlocks the grant for V6 / V6-Wild. ``allow_free_preview`` is set only
        after the caller reserved this month's one-per-model preview slot.
        """
        if allow_free_preview:
            return
        if await self._is_pro(user_id):
            return
        if model_allows_free_grant(
            model,
            is_free_plan=True,
            has_pack_this_month=await self.premium_unlocked(user_id),
        ):
            return
        raise _upgrade_error(
            f"{_premium_label(model)} requires purchased credits. "
            "Buy a credit pack to use it on the Free plan.",
            required=0,
            available=0,
        )

    async def _is_pro(self, user_id: UUID) -> bool:
        """Pro <=> at least one live credit pack lot (see tier_service)."""
        return bool(await self._store.live_pack_expiry(user_id))

    async def premium_unlocked(self, user_id: UUID) -> bool:
        """Whether a Free-plan user may use V6-Pro / V6-Wild.

        True while Pro (live pack lot), after a completed pack purchase in the
        current month, or while the wallet holds more than the monthly grant (a
        pack bought earlier whose credits are still live).
        """
        if await self._is_pro(user_id):
            return True
        if await self._store.has_completed_topup_this_month(user_id):
            return True
        if self._credit_repo is not None:
            wallet_units = int(await self._credit_repo.get_balance(user_id))
            return units_to_credits(wallet_units) > FREE_MONTHLY_CREDITS
        return False

    async def refund(self, user_id: UUID, charge: WebMusicCharge) -> None:
        if charge.amount_credits <= 0 or charge.path == "included":
            return
        if charge.path == "v3":
            await self._billing.refund(
                user_id=user_id,
                op=charge.op,
                amount_credits=float(charge.amount_credits),
                ref_id=charge.ref_id,
                product="web_music",
            )
            return
        if self._credit_service is None:
            return
        await self._credit_service.refund_credits(
            str(user_id),
            charge.amount_credits,
            f"web_music_{charge.op}",
            reference_id=charge.ref_id,
        )

    async def spendable_credits(self, user_id: UUID) -> tuple[int, int, bool]:
        """Return (spendable, music_credits, has_paid_web)."""
        await self._grant.ensure_daily_grant(user_id)
        await self._grant.ensure_period_grant(user_id)
        _op, music_credits, _quote = await self.quote_credits(user_id, "music")
        v3_balance = int(units_to_credits(int(await self._credit_repo.get_balance(user_id))))
        paid_web = await self._has_paid_web_subscription(user_id)
        return v3_balance, music_credits, paid_web

    async def _charge_v3(
        self,
        user_id: UUID,
        op: str,
        amount: int,
        *,
        ref_id: str | None,
        model: str | None = None,
    ) -> WebMusicCharge:
        try:
            await self._billing.charge(
                user_id=user_id,
                op=op,
                ref_id=ref_id,
                product="web_music",
                model=model,
            )
        except InsufficientCreditsError as exc:
            details = getattr(exc, "details", None) or {}
            available = int(details.get("current_balance") or 0)
            raise _upgrade_error(
                f"Insufficient credits. You need {amount} credits per song. "
                f"You have {available} credits.",
                required=amount,
                available=available,
            ) from exc
        return WebMusicCharge(path="v3", op=op, amount_credits=amount, ref_id=ref_id)

    async def _charge_v2(
        self,
        user_id: UUID,
        op: str,
        amount: int,
        *,
        ref_id: str | None,
    ) -> WebMusicCharge:
        from platform_api.services.v2.credit_service import InsufficientCreditsError as V2CreditsError

        if self._credit_service is None:
            raise _upgrade_error(
                "Credit system unavailable. Please try again later.",
                required=amount,
                available=0,
            )
        try:
            await self._credit_service.consume_credits(
                user_id=str(user_id),
                amount=amount,
                source=f"web_music_{op}",
                reference_id=ref_id,
            )
        except V2CreditsError as exc:
            raise _upgrade_error(str(exc), required=amount, available=0) from exc
        return WebMusicCharge(path="v2", op=op, amount_credits=amount, ref_id=ref_id)
