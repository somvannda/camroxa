"""Itemized pricing for split draft generation (title / album / lyric slots)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from platform_api.ai.purposes.draft_routing import DraftRouting
from platform_api.exceptions import ExternalServiceError, ValidationError


class PricingLookup(Protocol):
    """Minimal pricing interface used by draft billing helpers."""

    async def get_price(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str | None = None,
    ) -> int | None:
        ...


class DraftEnforcementProtocol(Protocol):
    """Minimal enforcement surface for per-slot draft billing."""

    async def deduct_for_operation(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
        *,
        sub_model: str | None = None,
    ) -> int: ...

    async def refund_failed_operation(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
        *,
        charged_credit_units: int = 0,
        sub_model: str | None = None,
        reason: str,
        ref_id: str | None = None,
        list_credit_units: int | None = None,
        prior_ledger_recorded: bool = True,
        count: int = 1,
    ) -> None: ...


@dataclass(frozen=True)
class DraftBillingLineItem:
    operation: str
    provider: str
    model: str | None
    amount_units: int

    def to_metadata(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "provider": self.provider,
            "model": self.model,
            "sub_model": self.model,
            "amount_units": self.amount_units,
        }


def draft_billing_slots(
    routing: DraftRouting,
    *,
    include_title: bool = True,
    include_album: bool = True,
) -> list[tuple[str, str, str | None]]:
    """Return (operation, provider, sub_model) slots that will run for one draft."""
    slots: list[tuple[str, str, str | None]] = [
        ("lyric", str(routing.lyric.provider), routing.lyric.sub_model),
    ]
    if include_title:
        slots.append(("title", str(routing.title.provider), routing.title.sub_model))
    if include_album:
        slots.append(("album", str(routing.album.provider), routing.album.sub_model))
    return slots


async def deduct_split_draft_billing(
    enforcement: DraftEnforcementProtocol,
    *,
    user_id: UUID,
    channel_profile_id: UUID | None,
    draft_routing: DraftRouting,
    include_title: bool = True,
    include_album: bool = True,
    pricing: PricingLookup | None = None,
) -> tuple[int, int]:
    """Deduct plan meter / wallet for each LLM draft slot (matches batch billing).

    Returns:
        (charged_credit_units, list_credit_units) — charged is wallet spend
        (0 on plan allowance); list is sum of pricing list units for COGS.
    """
    slots = draft_billing_slots(
        draft_routing,
        include_title=include_title,
        include_album=include_album,
    )
    charged_total = 0
    list_total = 0
    billed_slots = 0
    try:
        for operation_type, provider, sub_model in slots:
            charged = await enforcement.deduct_for_operation(
                user_id,
                channel_profile_id,
                operation_type,
                provider,
                sub_model=sub_model,
            )
            billed_slots += 1
            charged_total += int(charged or 0)
            if charged > 0:
                list_total += int(charged)
            elif pricing is not None:
                try:
                    list_price = await pricing.get_price(
                        provider, operation_type, sub_model
                    )
                    list_total += int(list_price or 0)
                except Exception:
                    pass
        return charged_total, list_total
    except Exception:
        if billed_slots > 0:
            try:
                await enforcement.refund_failed_operation(
                    user_id,
                    channel_profile_id,
                    "lyric",
                    str(slots[0][1]),
                    charged_credit_units=charged_total,
                    sub_model=slots[0][2],
                    reason="draft_generation_failed",
                    list_credit_units=list_total or None,
                    prior_ledger_recorded=True,
                    count=billed_slots,
                )
            except Exception:
                pass
        raise


async def _get_slot_price(
    pricing: PricingLookup,
    *,
    provider: str,
    operation: str,
    sub_model: str | None,
) -> int:
    model_label = str(sub_model or "default")
    try:
        price = await pricing.get_price(provider, operation, sub_model)
    except ExternalServiceError as exc:
        raise ValidationError(
            "Draft generation pricing is not configured. "
            f"Add an approved pricing row for provider '{provider}', operation '{operation}', "
            f"model '{model_label}'.",
            details={
                "provider": provider,
                "operation": operation,
                "sub_model": sub_model,
                "error": str(exc),
            },
        ) from exc
    if price is None:
        raise ValidationError(
            "Draft generation pricing is not configured.",
            details={
                "provider": provider,
                "operation": operation,
                "sub_model": sub_model,
            },
        )
    return int(price)


async def calculate_split_draft_billing(
    pricing: PricingLookup,
    routing: DraftRouting,
    *,
    include_title: bool = True,
    include_album: bool = True,
) -> tuple[int, list[DraftBillingLineItem]]:
    """Return total micro-units and per-slot line items for one split draft."""
    line_items: list[DraftBillingLineItem] = []

    lyric_amount = await _get_slot_price(
        pricing,
        provider=routing.lyric.provider,
        operation="lyric",
        sub_model=routing.lyric.sub_model,
    )
    line_items.append(
        DraftBillingLineItem(
            operation="lyric",
            provider=routing.lyric.provider,
            model=routing.lyric.sub_model,
            amount_units=lyric_amount,
        )
    )

    if include_title:
        title_amount = await _get_slot_price(
            pricing,
            provider=routing.title.provider,
            operation="title",
            sub_model=routing.title.sub_model,
        )
        line_items.append(
            DraftBillingLineItem(
                operation="title",
                provider=routing.title.provider,
                model=routing.title.sub_model,
                amount_units=title_amount,
            )
        )

    if include_album:
        album_amount = await _get_slot_price(
            pricing,
            provider=routing.album.provider,
            operation="album",
            sub_model=routing.album.sub_model,
        )
        line_items.append(
            DraftBillingLineItem(
                operation="album",
                provider=routing.album.provider,
                model=routing.album.sub_model,
                amount_units=album_amount,
            )
        )

    return sum(item.amount_units for item in line_items), line_items


async def calculate_split_draft_price(
    pricing: PricingLookup,
    routing: DraftRouting,
    *,
    include_title: bool = True,
    include_album: bool = True,
) -> int:
    """Sum micro-unit prices for LLM slots that will run in one split draft."""
    total, _ = await calculate_split_draft_billing(
        pricing,
        routing,
        include_title=include_title,
        include_album=include_album,
    )
    return total


async def calculate_batch_draft_cost(
    pricing: PricingLookup,
    routing: DraftRouting,
    song_count: int,
) -> int:
    """Estimate draft LLM cost for a batch.

    Song 1 runs title + album + lyric. Later songs reuse the batch album, so only
    title + lyric are billed.
    """
    if song_count <= 0:
        return 0
    first_song = await calculate_split_draft_price(
        pricing,
        routing,
        include_title=True,
        include_album=True,
    )
    if song_count == 1:
        return first_song
    subsequent = await calculate_split_draft_price(
        pricing,
        routing,
        include_title=True,
        include_album=False,
    )
    return first_song + subsequent * (song_count - 1)
