"""Quote / charge / refund against the shared credit_wallets + credit_pricing tables."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from platform_api.exceptions import InsufficientCreditsError, NotFoundError, ValidationError
from platform_api.services.credit_units import CREDIT_SCALE, credits_to_units, units_to_credits
from platform_api.services.pricing_display import credit_reset_label
from platform_api.services.v3.list_prices import (
    music_credits_per_generate,
    overlay_plan_list_prices,
    resolve_all_op_list_credits,
    resolve_op_list_units,
)
from platform_api.services.v3.ops import SUPPORTED_OPS
from platform_api.services.v3.store import V3BillingStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QuoteResult:
    op: str
    amount_credits: float
    amount_units: int
    source: str
    plan_id: str | None
    waived: bool = False
    included: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "amount_credits": self.amount_credits,
            "amount_units": self.amount_units,
            "source": self.source,
            "plan_id": self.plan_id,
            "waived": self.waived,
            "included": self.included,
        }


class CreditsOnlyBillingService:
    def __init__(
        self,
        *,
        store: V3BillingStore,
        credit_repo: Any,
        pricing_service: Any,
        enforcement: Any | None = None,
        ai_routing_service: Any | None = None,
    ) -> None:
        self._store = store
        self._credit_repo = credit_repo
        self._pricing = pricing_service
        self._enforcement = enforcement
        self._ai_routing = ai_routing_service

    async def _music_pricing_provider(self) -> str | None:
        """Routed provider for the ``music`` op, or None when unavailable.

        AI Routing is the single admin switch: selecting ``camxora_music_api``
        charges its (cheaper) row, selecting ``suno`` charges the Suno row. A
        routing miss or a provider without active keys falls back to the static
        chain so pricing/plan pages never hard-fail on a config gap.
        """
        if self._ai_routing is None:
            return None
        try:
            routing = await self._ai_routing.resolve("music")
        except Exception:
            logger.debug("music routing lookup failed; using default price chain", exc_info=True)
            return None
        provider = str(getattr(routing, "provider", "") or "").strip().lower()
        return provider or None

    async def list_pricing(self) -> list[dict[str, Any]]:
        return await self._pricing.get_all_pricing()

    async def wallet_view(self, user_id: UUID) -> dict[str, Any]:
        balance_units = int(await self._credit_repo.get_balance(user_id))
        grant_units = await self._store.grant_remaining_units(user_id)
        lots = await self._store.list_lots(user_id)
        plan = await self._store.resolve_charge_plan(user_id)
        daily = int((plan or {}).get("daily_credits") or 0)
        monthly = int((plan or {}).get("monthly_credits") or 0)
        return {
            "user_id": str(user_id),
            "balance_credits": units_to_credits(balance_units),
            "balance_units": balance_units,
            "grant_remaining_credits": units_to_credits(grant_units),
            "grant_remaining_units": grant_units,
            "plan": plan,
            "reset_label": credit_reset_label(daily_credits=daily, monthly_credits=monthly),
            "lots": [
                {
                    "id": str(lot["id"]),
                    "tag": lot["tag"],
                    "amount_credits": units_to_credits(int(lot["amount_units"])),
                    "remaining_credits": units_to_credits(int(lot["remaining_units"])),
                    "expires_at": lot.get("expires_at"),
                    "period_start": lot.get("period_start"),
                }
                for lot in lots
            ],
        }

    async def quote(
        self,
        *,
        op: str,
        user_id: UUID | None = None,
        plan_id: UUID | None = None,
        waive: bool = False,
    ) -> QuoteResult:
        operation = self._normalize_op(op)
        if waive:
            return QuoteResult(
                op=operation,
                amount_credits=0,
                amount_units=0,
                source="waive",
                plan_id=str(plan_id) if plan_id else None,
                waived=True,
                included=True,
            )

        plan = None
        if plan_id is not None:
            plan = await self._store.get_plan(plan_id)
            if plan is None:
                raise NotFoundError("Plan not found.", details={"plan_id": str(plan_id)})
        elif user_id is not None:
            plan = await self._store.get_plan_for_user(user_id)

        music_provider = (
            await self._music_pricing_provider() if operation == "music" else None
        )
        units = await resolve_op_list_units(
            self._pricing, operation, music_provider=music_provider
        )
        return QuoteResult(
            op=operation,
            amount_credits=units_to_credits(units),
            amount_units=units,
            source="credit_pricing",
            plan_id=plan["id"] if plan else None,
            included=units == 0,
        )

    async def op_list_credits(self) -> dict[str, float]:
        music_provider = await self._music_pricing_provider()
        return await resolve_all_op_list_credits(
            self._pricing, music_provider=music_provider
        )

    async def music_credits_per_generate(self) -> int | float:
        return music_credits_per_generate(await self.op_list_credits())

    def apply_list_prices(
        self,
        plan: dict[str, Any],
        op_credits: dict[str, float],
        *,
        overlay_ops: bool = False,
    ) -> dict[str, Any]:
        return overlay_plan_list_prices(plan, op_credits, overlay_ops=overlay_ops)

    async def charge(
        self,
        *,
        user_id: UUID,
        op: str,
        ref_id: str | None = None,
        waive: bool = False,
        plan_id: UUID | None = None,
        product: str | None = None,
    ) -> dict[str, Any]:
        quote = await self.quote(op=op, user_id=user_id, plan_id=plan_id, waive=waive)
        if self._enforcement is not None and not waive:
            await self._enforcement.enforce_fail_absorb_budget(user_id)

        if quote.amount_units <= 0:
            return {
                **quote.to_dict(),
                "user_id": str(user_id),
                "charged": False,
                "balance_units": int(await self._credit_repo.get_balance(user_id)),
            }

        reason = f"v3_{quote.op}"
        if ref_id:
            existing = await self._existing_debit(user_id, reason, ref_id)
            if existing:
                return {
                    **quote.to_dict(),
                    "user_id": str(user_id),
                    "charged": True,
                    "idempotent": True,
                    "balance_units": int(await self._credit_repo.get_balance(user_id)),
                }

        metadata = {
            "billing": "wallet",
            "source": "v3",
            "op": quote.op,
            "operation": quote.op,
            "quote_source": quote.source,
        }
        if product:
            # Product context makes web vs desktop attribution provable for
            # image/lyric/title charges, which share the same reason strings.
            metadata["product"] = str(product)[:32]
        ok = await self._credit_repo.atomic_deduct(
            user_id,
            quote.amount_units,
            reason,
            ref_id=ref_id,
            metadata=metadata,
        )
        if not ok:
            current = int(await self._credit_repo.get_balance(user_id))
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": quote.amount_credits,
                    "required_units": quote.amount_units,
                    "current_balance": units_to_credits(current),
                },
            )
        return {
            **quote.to_dict(),
            "user_id": str(user_id),
            "charged": True,
            "idempotent": False,
            "balance_units": int(await self._credit_repo.get_balance(user_id)),
        }

    async def refund(
        self,
        *,
        user_id: UUID,
        op: str,
        amount_credits: float | None = None,
        ref_id: str | None = None,
        absorb: bool = False,
        product: str | None = None,
    ) -> dict[str, Any]:
        operation = self._normalize_op(op)
        if amount_credits is None:
            quote = await self.quote(op=operation, user_id=user_id)
            units = quote.amount_units
            credits = quote.amount_credits
        else:
            if amount_credits < 0:
                raise ValidationError("Refund amount cannot be negative.")
            units = credits_to_units(amount_credits)
            credits = float(amount_credits)

        if units > 0:
            reason = f"v3_refund_{operation}"
            metadata = {
                "billing": "platform_absorb" if absorb else "wallet_refund",
                "source": "v3",
                "op": operation,
            }
            if product:
                metadata["product"] = str(product)[:32]
            # A stable ref_id makes the refund idempotent, so a retried or
            # cross-process refund of the same charge cannot double-credit.
            refund_once = getattr(self._credit_repo, "refund_once", None)
            if ref_id and callable(refund_once):
                await refund_once(
                    user_id,
                    units,
                    reason=reason,
                    ref_id=ref_id,
                    metadata=metadata,
                )
            else:
                await self._credit_repo.refund(
                    user_id,
                    units,
                    reason=reason,
                    ref_id=ref_id,
                    metadata=metadata,
                )
        used = None
        if absorb and self._enforcement is not None:
            used = await self._enforcement.record_fail_absorb(user_id)
        return {
            "user_id": str(user_id),
            "op": operation,
            "amount_credits": credits,
            "amount_units": units,
            "absorb": absorb,
            "fail_absorb_used": used,
            "balance_units": int(await self._credit_repo.get_balance(user_id)),
            "balance_credits": units_to_credits(int(await self._credit_repo.get_balance(user_id))),
        }

    async def _existing_debit(self, user_id: UUID, reason: str, ref_id: str) -> bool:
        getter = getattr(self._credit_repo, "has_transaction", None)
        if getter is None:
            return False
        return bool(await getter(user_id, reason=reason, ref_id=ref_id))

    @staticmethod
    def _normalize_op(op: str) -> str:
        value = str(op or "").strip().lower()
        aliases = {
            "song": "music",
            "music_generation": "music",
            "suno": "music",
            "lyric": "lyric",
            "lyrics": "lyric",
            "web_music_lyrics": "lyric",
            "web_music_style": "style",
            "background_image": "image",
            "thumbnail_image": "image",
            "video_manual": "video",
            "video_merge": "merge",
        }
        value = aliases.get(value, value)
        if value not in SUPPORTED_OPS:
            raise ValidationError(
                f"Unsupported operation '{op}'.",
                details={"op": op, "supported": list(SUPPORTED_OPS)},
            )
        return value


# Keep CREDIT_SCALE imported for callers that convert lots.
_ = CREDIT_SCALE
