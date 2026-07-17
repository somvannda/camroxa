"""Generate credit pricing rows from model costs and target margin."""

from __future__ import annotations

from typing import Any, Protocol

from platform_api.exceptions import ValidationError
from platform_api.services.credit_units import (
    cost_units_to_pricing_units,
    usd_to_cost_units,
)
from platform_api.services.model_cost_estimates import estimate_cost_usd
from platform_api.services.pricing_keys import normalize_pricing_sub_model, pricing_lookup_key
from platform_api.services.pricing_sync_service import (
    RequiredPricingPair,
    collect_required_pricing_pairs,
)


class ModelCostReaderProtocol(Protocol):
    async def get_all(self) -> list[dict[str, Any]]: ...

    async def get_by_key(
        self, ai_service: str, sub_model: str, operation_type: str
    ) -> dict[str, Any] | None: ...


class PricingWriterProtocol(Protocol):
    async def get_all(self) -> list[dict[str, Any]]: ...

    async def create(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
        needs_review: bool = False,
    ) -> dict[str, Any]: ...

    async def update(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
    ) -> dict[str, Any] | None: ...


def compute_credit_prices(
    *,
    cost_usd: float,
    global_credit_value: float,
    margin_percent: float,
) -> tuple[int, int]:
    """Return (cost_units, pricing_units) from USD cost and target margin on revenue."""
    if global_credit_value <= 0:
        raise ValidationError(
            "Global credit value must be configured before generating pricing.",
            details={"global_credit_value": global_credit_value},
        )
    if margin_percent < 0 or margin_percent >= 100:
        raise ValidationError(
            "margin_percent must be between 0 and 99.99.",
            details={"margin_percent": margin_percent},
        )

    cost_units = usd_to_cost_units(max(0.0, float(cost_usd)), global_credit_value)
    pricing_units = cost_units_to_pricing_units(cost_units, margin_percent)
    return cost_units, pricing_units


def resolve_model_cost_usd(
    *,
    ai_service: str,
    sub_model: str,
    operation_type: str,
    cost_rows: list[dict[str, Any]],
) -> float | None:
    """Lookup model cost with exact model, then registry estimate."""
    normalized_model = normalize_pricing_sub_model(sub_model)
    for row in cost_rows:
        if (
            row.get("ai_service") == ai_service
            and normalize_pricing_sub_model(row.get("sub_model")) == normalized_model
            and row.get("operation_type") == operation_type
        ):
            return float(row.get("cost_usd") or 0)

    return estimate_cost_usd(
        ai_service=ai_service,
        sub_model=normalized_model,
        operation_type=operation_type,
    )


class PricingGeneratorService:
    def __init__(
        self,
        *,
        model_cost_repo: ModelCostReaderProtocol,
        pricing_repo: PricingWriterProtocol,
    ) -> None:
        self._model_cost_repo = model_cost_repo
        self._pricing_repo = pricing_repo

    async def generate_from_costs(
        self,
        *,
        margin_percent: float,
        global_credit_value: float,
        assignments: dict[str, dict[str, Any]],
        text_fallback_chain: list[dict[str, Any]],
        image_fallback_chain: list[dict[str, Any]],
        overwrite_existing: bool = False,
        mark_needs_review: bool = True,
    ) -> dict[str, Any]:
        """Create or update credit_pricing rows for all routing-required pairs."""
        required_pairs = collect_required_pricing_pairs(
            assignments=assignments,
            text_fallback_chain=text_fallback_chain,
            image_fallback_chain=image_fallback_chain,
        )
        cost_rows = await self._model_cost_repo.get_all()
        existing_pricing = await self._pricing_repo.get_all()
        existing_keys = {
            pricing_lookup_key(
                str(row["ai_service"]),
                str(row["operation_type"]),
                str(row.get("sub_model") or ""),
            )
            for row in existing_pricing
        }

        created: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        missing_costs: list[dict[str, str]] = []

        for pair in required_pairs:
            key = pricing_lookup_key(pair.ai_service, pair.operation_type, pair.sub_model)
            if key in existing_keys and not overwrite_existing:
                skipped.append(
                    {
                        "ai_service": pair.ai_service,
                        "operation_type": pair.operation_type,
                        "sub_model": pair.sub_model,
                    }
                )
                continue

            cost_usd = resolve_model_cost_usd(
                ai_service=pair.ai_service,
                sub_model=pair.sub_model,
                operation_type=pair.operation_type,
                cost_rows=cost_rows,
            )
            if cost_usd is None:
                missing_costs.append(
                    {
                        "ai_service": pair.ai_service,
                        "operation_type": pair.operation_type,
                        "sub_model": pair.sub_model,
                    }
                )
                continue

            cost_units, pricing_units = compute_credit_prices(
                cost_usd=cost_usd,
                global_credit_value=global_credit_value,
                margin_percent=margin_percent,
            )

            if key in existing_keys:
                row = await self._pricing_repo.update(
                    pair.ai_service,
                    pair.operation_type,
                    pricing_units,
                    cost_units,
                    sub_model=pair.sub_model,
                )
                if row is not None:
                    updated.append(row)
                continue

            row = await self._pricing_repo.create(
                pair.ai_service,
                pair.operation_type,
                pricing_units,
                cost_units,
                sub_model=pair.sub_model,
                needs_review=mark_needs_review,
            )
            created.append(row)
            existing_keys.add(key)

        return {
            "created_count": len(created),
            "updated_count": len(updated),
            "skipped_existing_count": len(skipped),
            "missing_cost_count": len(missing_costs),
            "created": created,
            "updated": updated,
            "missing_costs": missing_costs,
        }
