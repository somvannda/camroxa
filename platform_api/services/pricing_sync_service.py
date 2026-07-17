"""Helpers to derive required credit pricing from AI routing configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_api.ai.types import (
    IMAGE_OPERATIONS,
    OPERATION_SERVICE_TYPE,
    TEXT_OPERATIONS,
    Operation,
    ServiceType,
    is_suno_lyric_routing,
)
from platform_api.services.credit_units import CREDIT_SCALE, MIN_CREDIT_UNITS
from platform_api.services.pricing_keys import normalize_pricing_sub_model, pricing_lookup_key


def _routing_entry_active(item: dict[str, Any]) -> bool:
    value = item.get("is_active", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "off"}
    return bool(value)


# Sensible per-operation defaults (micro-units) when no sibling pricing exists.
_OPERATION_DEFAULT_CREDITS: dict[str, int] = {
    "channel_name": 3 * CREDIT_SCALE,
    "channel_description": 3 * CREDIT_SCALE,
    "channel_keywords": 3 * CREDIT_SCALE,
    "channel_tags": 3 * CREDIT_SCALE,
    "lyric": 5 * CREDIT_SCALE,
    "title": 3 * CREDIT_SCALE,
    "album": 3 * CREDIT_SCALE,
    "channel_logo": 5 * CREDIT_SCALE,
    "channel_cover": 8 * CREDIT_SCALE,
    "background_image": 5 * CREDIT_SCALE,
    "thumbnail_image": 5 * CREDIT_SCALE,
    # List price at ~20% margin over $0.06 music COGS (GCV $0.01 → 6 cost credits).
    "music": 75 * CREDIT_SCALE // 10,  # 7.5 display credits
}


@dataclass(frozen=True)
class RequiredPricingPair:
    ai_service: str
    operation_type: str
    sub_model: str
    source: str


def collect_required_pricing_pairs(
    *,
    assignments: dict[str, dict[str, Any]],
    text_fallback_chain: list[dict[str, Any]],
    image_fallback_chain: list[dict[str, Any]],
) -> list[RequiredPricingPair]:
    """Return every (ai_service, operation_type, sub_model) pair routing can bill."""
    seen: set[tuple[str, str, str]] = set()
    required: list[RequiredPricingPair] = []

    def _add(
        ai_service: str,
        operation_type: str,
        sub_model: str | None,
        source: str,
    ) -> None:
        key = pricing_lookup_key(ai_service, operation_type, sub_model)
        if not key[0] or not key[1] or key in seen:
            return
        seen.add(key)
        required.append(
            RequiredPricingPair(
                ai_service=key[0],
                operation_type=key[1],
                sub_model=key[2],
                source=source,
            )
        )

    for operation, assignment in assignments.items():
        if not _routing_entry_active(assignment):
            continue
        provider = str(assignment.get("provider") or "").strip()
        sub_model = assignment.get("sub_model")
        if provider:
            _add(provider, operation, sub_model, "primary")

    for index, item in enumerate(text_fallback_chain):
        if not _routing_entry_active(item):
            continue
        provider = str(item.get("provider") or "").strip()
        if not provider:
            continue
        sub_model = item.get("sub_model")
        for text_operation in TEXT_OPERATIONS:
            if provider == "suno" and not is_suno_lyric_routing(
                provider=provider, operation=text_operation
            ):
                continue
            _add(provider, text_operation, sub_model, f"text_fallback_{index + 1}")

    for index, item in enumerate(image_fallback_chain):
        if not _routing_entry_active(item):
            continue
        provider = str(item.get("provider") or "").strip()
        if not provider:
            continue
        sub_model = item.get("sub_model")
        for image_operation in IMAGE_OPERATIONS:
            _add(provider, image_operation, sub_model, f"image_fallback_{index + 1}")

    return required


def _service_type_for_operation(operation_type: str) -> ServiceType | None:
    try:
        return OPERATION_SERVICE_TYPE[Operation(operation_type)]
    except ValueError:
        return None


def suggest_pricing_values(
    *,
    ai_service: str,
    operation_type: str,
    sub_model: str | None = None,
    existing_entries: list[dict[str, Any]],
) -> tuple[int, int]:
    """Suggest (credits_per_operation, external_cost_cents) for a missing row."""
    target_service = _service_type_for_operation(operation_type)
    target_model = normalize_pricing_sub_model(sub_model)

    same_provider_credits: list[int] = []
    same_provider_costs: list[int] = []
    same_operation_credits: list[int] = []
    same_operation_costs: list[int] = []

    for entry in existing_entries:
        entry_service = entry.get("ai_service")
        entry_operation = entry.get("operation_type")
        entry_model = normalize_pricing_sub_model(entry.get("sub_model"))
        credits = int(entry.get("credits_per_operation") or 0)
        cost = entry.get("external_cost_cents")
        if credits <= 0:
            continue

        if entry_service == ai_service:
            same_provider_credits.append(credits)
            if cost is not None:
                same_provider_costs.append(int(cost))
            if entry_operation == operation_type and entry_model == target_model:
                return credits, int(cost or MIN_CREDIT_UNITS)
            if entry_operation == operation_type and not target_model and not entry_model:
                return credits, int(cost or MIN_CREDIT_UNITS)

        if entry_operation == operation_type:
            same_operation_credits.append(credits)
            if cost is not None:
                same_operation_costs.append(int(cost))

        if (
            target_service is not None
            and entry_service == ai_service
            and entry_operation
        ):
            try:
                entry_st = OPERATION_SERVICE_TYPE[Operation(str(entry_operation))]
            except ValueError:
                continue
            if entry_st == target_service:
                same_provider_credits.append(credits)
                if cost is not None:
                    same_provider_costs.append(int(cost))

    if same_provider_credits:
        credits = sorted(same_provider_credits)[len(same_provider_credits) // 2]
        cost = (
            sorted(same_provider_costs)[len(same_provider_costs) // 2]
            if same_provider_costs
            else max(MIN_CREDIT_UNITS, credits // 2)
        )
        return credits, cost

    if same_operation_credits:
        credits = sorted(same_operation_credits)[len(same_operation_credits) // 2]
        cost = (
            sorted(same_operation_costs)[len(same_operation_costs) // 2]
            if same_operation_costs
            else max(MIN_CREDIT_UNITS, credits // 2)
        )
        return credits, cost

    credits = _OPERATION_DEFAULT_CREDITS.get(operation_type, 3 * CREDIT_SCALE)
    if target_service == ServiceType.IMAGE_GENERATION:
        credits = max(credits, 5 * CREDIT_SCALE)
        return credits, max(MIN_CREDIT_UNITS, credits // 2)
    if target_service == ServiceType.MUSIC_GENERATION:
        # Suno pack economics: COGS $0.06 → 6 cost credits; list 7.5 (~20% margin).
        list_units = 75 * CREDIT_SCALE // 10
        cost_units = 6 * CREDIT_SCALE
        return max(credits, list_units), cost_units
    return credits, max(MIN_CREDIT_UNITS, credits // 2)
