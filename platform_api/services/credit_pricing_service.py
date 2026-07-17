"""Credit pricing service for per-service operation pricing configuration.

Provides CRUD operations for credit pricing: configure per-service pricing
(ai_service + operation_type unique), validate credits_per_operation
in [1, 10000], store external cost, and compute margin.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from platform_api.exceptions import (
    DuplicateError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from platform_api.models.domain import MarginDetails
from platform_api.models.enums import AIService, ServiceAvailability

from platform_api.services.credit_units import (
    CREDIT_SCALE,
    MAX_CREDIT_UNITS,
    MIN_CREDIT_UNITS,
    units_to_credits,
)
from platform_api.services.pricing_keys import (
    normalize_pricing_sub_model,
    normalize_suno_pricing_sub_model,
    pricing_lookup_key,
)

logger = logging.getLogger(__name__)

# Suno pack cost basis: 12 credits × ($50/10k) = $0.06 → 6 display credits at GCV $0.01.
MIN_MUSIC_COST_UNITS = 6 * CREDIT_SCALE
_MUSIC_OPERATIONS = frozenset({"music", "music_generation", "suno"})


# ---------------------------------------------------------------------------
# Protocol interfaces for dependency injection
# ---------------------------------------------------------------------------


class CreditPricingRepositoryProtocol(Protocol):
    """Protocol for credit pricing repository operations."""

    async def get_all(self) -> list[dict[str, Any]]:
        """Return all configured pricing entries."""
        ...

    async def get_by_service_and_operation(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        """Return a pricing entry for an ai_service/operation/model combination."""
        ...

    async def create(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
        needs_review: bool = False,
    ) -> dict[str, Any]:
        """Create a new pricing entry. Raises on duplicate."""
        ...

    async def approve(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        ...

    async def approve_many(self, pairs: list[tuple[str, str, str]]) -> int:
        ...

    async def update(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        """Update an existing pricing entry. Returns None if not found."""
        ...

    async def delete(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str = "",
    ) -> bool:
        """Delete a pricing entry. Returns True if deleted, False if not found."""
        ...

    async def delete_all(self, *, ai_service: str | None = None) -> int:
        """Delete all pricing entries. Returns count deleted."""
        ...


async def lookup_pricing_entry(
    pricing_repo: CreditPricingRepositoryProtocol,
    ai_service: str,
    operation_type: str,
    sub_model: str | None = None,
) -> dict[str, Any] | None:
    """Resolve pricing for a model, falling back to provider-wide default."""
    service = str(ai_service or "").strip()
    operation = str(operation_type or "").strip()
    model = normalize_pricing_sub_model(sub_model)
    if service.lower() == "suno" and operation.lower() in {"music_generation", "music", "suno"}:
        model = normalize_suno_pricing_sub_model(model)

    operations_to_try = [operation]
    if service.lower() == "suno" and operation.lower() in {"music_generation", "music", "suno"}:
        operations_to_try = ["music_generation", "music"]

    for op in operations_to_try:
        entry = await pricing_repo.get_by_service_and_operation(
            service, op, model
        )
        if entry is None and model:
            entry = await pricing_repo.get_by_service_and_operation(
                service, op, ""
            )
        if entry is not None:
            return entry
    return None


class KeyPoolQueryProtocol(Protocol):
    """Protocol for querying key pool entries to determine service availability."""

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return rows."""
        ...


# ---------------------------------------------------------------------------
# Credit Pricing Service
# ---------------------------------------------------------------------------


class CreditPricingService:
    """Service for managing per-model credit pricing configuration.

    Manages the Admin-configurable pricing table that maps AI model operations
    to their credit cost. Enforces validation rules and computes margins.

    Args:
        pricing_repo: Repository implementing CreditPricingRepositoryProtocol.
    """

    def __init__(
        self,
        pricing_repo: CreditPricingRepositoryProtocol,
        db_pool: KeyPoolQueryProtocol | None = None,
    ) -> None:
        self._pricing_repo = pricing_repo
        self._db_pool = db_pool

    def _compute_margin(
        self, credits_per_operation: int, external_cost_cents: int | None
    ) -> float | None:
        """Compute profit margin in display credits."""
        if external_cost_cents is None:
            return None
        return units_to_credits(credits_per_operation) - units_to_credits(external_cost_cents)

    def _validate_credit_units(self, credits_per_operation: int) -> None:
        """Validate stored micro-units for a pricing row."""
        if not isinstance(credits_per_operation, int):
            raise ValidationError(
                "credits_per_operation must be an integer.",
                details={"credits_per_operation": credits_per_operation},
            )
        if credits_per_operation < MIN_CREDIT_UNITS:
            raise ValidationError(
                f"credits_per_operation must be at least {MIN_CREDIT_UNITS} micro-units.",
                details={
                    "credits_per_operation": credits_per_operation,
                    "min_units": MIN_CREDIT_UNITS,
                    "max_units": MAX_CREDIT_UNITS,
                },
            )
        if credits_per_operation > MAX_CREDIT_UNITS:
            raise ValidationError(
                f"credits_per_operation must not exceed {MAX_CREDIT_UNITS} micro-units.",
                details={
                    "credits_per_operation": credits_per_operation,
                    "min_units": MIN_CREDIT_UNITS,
                    "max_units": MAX_CREDIT_UNITS,
                },
            )

    @staticmethod
    def _is_music_operation(operation_type: str) -> bool:
        return str(operation_type or "").strip().lower() in _MUSIC_OPERATIONS

    def _validate_pricing_economics(
        self,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> None:
        """Reject cost > sell and underpriced music cost basis (H9)."""
        if external_cost_cents is None:
            return
        if not isinstance(external_cost_cents, int):
            raise ValidationError(
                "external_cost_cents must be an integer.",
                details={"external_cost_cents": external_cost_cents},
            )
        if external_cost_cents < 0:
            raise ValidationError(
                "external_cost_cents must not be negative.",
                details={"external_cost_cents": external_cost_cents},
            )
        if external_cost_cents > credits_per_operation:
            raise ValidationError(
                "Provider cost cannot exceed sell price (cost > list credits).",
                details={
                    "error_code": "COST_EXCEEDS_SELL",
                    "credits_per_operation": credits_per_operation,
                    "external_cost_cents": external_cost_cents,
                },
            )
        if (
            self._is_music_operation(operation_type)
            and external_cost_cents < MIN_MUSIC_COST_UNITS
        ):
            raise ValidationError(
                "Music cost basis must be at least 6 credits "
                "($0.06 Suno pack at GCV $0.01).",
                details={
                    "error_code": "MUSIC_COST_BELOW_BASIS",
                    "operation_type": operation_type,
                    "external_cost_cents": external_cost_cents,
                    "min_music_cost_units": MIN_MUSIC_COST_UNITS,
                },
            )

    def _enrich_with_margin(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Add computed margin to a pricing entry dict."""
        entry["margin"] = self._compute_margin(
            entry["credits_per_operation"], entry.get("external_cost_cents")
        )
        return entry

    # -----------------------------------------------------------------------
    # Margin Computation & Service Availability
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_margin_details(
        credits_per_operation: int,
        external_cost_cents: int,
        global_credit_value: float | None,
    ) -> MarginDetails | None:
        """Pure computation of sell_price, profit_margin, profit_margin_percent.

        Returns None if global_credit_value is not configured.

        Args:
            credits_per_operation: Credits charged per operation.
            external_cost_cents: External provider cost in cents.
            global_credit_value: Dollar value of one credit, or None if not set.

        Returns:
            MarginDetails with sell_price_cents, profit_margin_cents, and
            profit_margin_percent, or None if global_credit_value is None.

        Requirements: 2.4, 3.4, 3.5
        """
        if global_credit_value is None:
            return None
        pricing_credits = units_to_credits(credits_per_operation)
        cost_credits = units_to_credits(external_cost_cents)
        sell_price_cents = round(pricing_credits * global_credit_value * 100)
        cost_usd_cents = round(cost_credits * global_credit_value * 100)
        profit_margin_cents = sell_price_cents - cost_usd_cents
        profit_margin_percent = (
            round((profit_margin_cents / sell_price_cents) * 100, 2)
            if sell_price_cents > 0
            else 0.0
        )
        return MarginDetails(
            sell_price_cents=sell_price_cents,
            profit_margin_cents=profit_margin_cents,
            profit_margin_percent=profit_margin_percent,
        )

    async def get_service_availability(self) -> list[dict[str, Any]]:
        """Query Key Pool to determine each AI service's operational status.

        For each provider in AIService enum values, checks api_key_entries:
        - "available" when at least one key has status='active'
        - "degraded" when keys exist but none has status='active'
        - "unavailable" when no key entries exist for that provider

        Returns:
            List of dicts with keys: ai_service (str), status (ServiceAvailability).

        Requirements: 4.1
        """
        if self._db_pool is None:
            # No db_pool configured — return all services as unavailable
            return [
                {"ai_service": service.value, "status": ServiceAvailability.UNAVAILABLE}
                for service in AIService
            ]

        results: list[dict[str, Any]] = []
        for service in AIService:
            rows = await self._db_pool.fetch(
                "SELECT status FROM api_key_entries WHERE provider = $1",
                service.value,
            )
            if not rows:
                status = ServiceAvailability.UNAVAILABLE
            elif any(row["status"] == "active" for row in rows):
                status = ServiceAvailability.AVAILABLE
            else:
                status = ServiceAvailability.DEGRADED
            results.append({"ai_service": service.value, "status": status})

        return results

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def get_all_pricing(self) -> list[dict[str, Any]]:
        """Return all configured model pricing with computed margins.

        Requirement 5.4: Returns all configured operations with credit charge,
        external API cost, and calculated margin.

        Returns:
            List of pricing entry dicts with keys: id, ai_service,
            operation_type, credits_per_operation, external_cost_cents, margin,
            created_at, updated_at.
        """
        entries = await self._pricing_repo.get_all()
        return [self._enrich_with_margin(e) for e in entries]

    async def get_price(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str | None = None,
    ) -> int:
        """Return credits_per_operation for an ai_service/operation/model combination.

        Lookup order: exact model row, then provider-wide default (sub_model='').

        Requirement 5.6: If no pricing is configured for the requested
        operation, raises ExternalServiceError to reject the generation request.

        Args:
            ai_service: The AI service identifier (e.g. "suno").
            operation_type: The operation type (e.g. "music_generation").
            sub_model: Optional model id from routing (e.g. "deepseek-chat").

        Returns:
            The integer credits cost for the operation.

        Raises:
            ExternalServiceError: If no pricing is configured for the
                ai_service/operation combination.
        """
        entry = await lookup_pricing_entry(
            self._pricing_repo, ai_service, operation_type, sub_model
        )
        if entry is None:
            model_label = normalize_pricing_sub_model(sub_model) or "default"
            raise ExternalServiceError(
                f"No pricing configured for ai_service '{ai_service}' "
                f"operation '{operation_type}' model '{model_label}'. "
                "This operation is not yet available.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": normalize_pricing_sub_model(sub_model),
                },
            )
        return entry["credits_per_operation"]

    async def set_price(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
        *,
        sub_model: str | None = None,
    ) -> dict[str, Any]:
        """Create or update pricing for an ai_service/operation combination.

        Requirement 5.1: Store ai_service, operation type,
        credits-per-operation, and external cost.
        Requirement 5.5: Validate credits_per_operation in [1, 10000].
        Requirement 5.7: Enforce unique constraint on (ai_service, operation_type).

        If the pricing entry already exists, it will be updated (Req 5.2).
        If it does not exist, a new entry is created.

        Args:
            ai_service: The AI service identifier.
            operation_type: The operation type.
            credits_per_operation: Credits charged per operation [1, 10000].
            external_cost_cents: Actual external API cost in cents (optional).

        Returns:
            The created or updated pricing entry dict with margin.

        Raises:
            ValidationError: If credits_per_operation is outside [1, 10000].
        """
        self._validate_credit_units(credits_per_operation)
        self._validate_pricing_economics(
            operation_type, credits_per_operation, external_cost_cents
        )
        model = normalize_pricing_sub_model(sub_model)

        # Try to update existing entry first
        existing = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type, model
        )
        if existing is not None:
            updated = await self._pricing_repo.update(
                ai_service,
                operation_type,
                credits_per_operation,
                external_cost_cents,
                sub_model=model,
            )
            if updated is None:
                raise NotFoundError(
                    "Pricing entry not found during update.",
                    details={
                        "ai_service": ai_service,
                        "operation_type": operation_type,
                        "sub_model": model,
                    },
                )
            logger.info(
                "Pricing updated: ai_service=%s, op=%s, model=%s, credits=%d",
                ai_service,
                operation_type,
                model or "default",
                credits_per_operation,
            )
            return self._enrich_with_margin(updated)

        # Create new entry
        created = await self._pricing_repo.create(
            ai_service,
            operation_type,
            credits_per_operation,
            external_cost_cents,
            sub_model=model,
        )
        logger.info(
            "Pricing created: ai_service=%s, op=%s, model=%s, credits=%d",
            ai_service,
            operation_type,
            model or "default",
            credits_per_operation,
        )
        return self._enrich_with_margin(created)

    async def create_price(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
        *,
        sub_model: str | None = None,
    ) -> dict[str, Any]:
        """Create pricing for an ai_service/operation combination (strict create).

        Unlike set_price, this raises DuplicateError if the entry already exists.
        Used by the POST /credits/pricing endpoint (Req 5.7).

        Args:
            ai_service: The AI service identifier.
            operation_type: The operation type.
            credits_per_operation: Credits charged per operation [1, 10000].
            external_cost_cents: Actual external API cost in cents (optional).

        Returns:
            The created pricing entry dict with margin.

        Raises:
            ValidationError: If credits_per_operation is outside [1, 10000].
            DuplicateError: If a pricing entry already exists for this combination.
        """
        self._validate_credit_units(credits_per_operation)
        self._validate_pricing_economics(
            operation_type, credits_per_operation, external_cost_cents
        )
        model = normalize_pricing_sub_model(sub_model)

        # Check for existing entry
        existing = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type, model
        )
        if existing is not None:
            raise DuplicateError(
                f"Pricing already exists for ai_service '{ai_service}' "
                f"operation '{operation_type}' model '{model or 'default'}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": model,
                },
            )

        created = await self._pricing_repo.create(
            ai_service,
            operation_type,
            credits_per_operation,
            external_cost_cents,
            sub_model=model,
        )
        logger.info(
            "Pricing created: ai_service=%s, op=%s, model=%s, credits=%d",
            ai_service,
            operation_type,
            model or "default",
            credits_per_operation,
        )
        return self._enrich_with_margin(created)

    async def update_price(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
        *,
        sub_model: str | None = None,
        lookup_sub_model: str | None = None,
    ) -> dict[str, Any]:
        """Update existing pricing for an ai_service/operation combination (strict update).

        Unlike set_price, this raises NotFoundError if the entry does not exist.
        Used by the PUT /credits/pricing endpoint (Req 5.2).

        Args:
            ai_service: The AI service identifier.
            operation_type: The operation type.
            credits_per_operation: Credits charged per operation [1, 10000].
            external_cost_cents: Actual external API cost in cents (optional).

        Returns:
            The updated pricing entry dict with margin.

        Raises:
            ValidationError: If credits_per_operation is outside [1, 10000].
            NotFoundError: If no pricing entry exists for this combination.
        """
        self._validate_credit_units(credits_per_operation)
        self._validate_pricing_economics(
            operation_type, credits_per_operation, external_cost_cents
        )
        model = normalize_pricing_sub_model(sub_model)
        lookup_model = normalize_pricing_sub_model(
            lookup_sub_model if lookup_sub_model is not None else sub_model
        )

        existing = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type, lookup_model
        )
        if existing is None:
            raise NotFoundError(
                f"No pricing found for ai_service '{ai_service}' "
                f"operation '{operation_type}' model '{lookup_model or 'default'}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": lookup_model,
                },
            )

        if lookup_model != model:
            await self._pricing_repo.delete(
                ai_service, operation_type, sub_model=lookup_model
            )
            created = await self._pricing_repo.create(
                ai_service,
                operation_type,
                credits_per_operation,
                external_cost_cents,
                sub_model=model,
            )
            return self._enrich_with_margin(created)

        updated = await self._pricing_repo.update(
            ai_service,
            operation_type,
            credits_per_operation,
            external_cost_cents,
            sub_model=model,
        )
        if updated is None:
            raise NotFoundError(
                "Pricing entry not found during update.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": model,
                },
            )
        logger.info(
            "Pricing updated: ai_service=%s, op=%s, model=%s, credits=%d",
            ai_service,
            operation_type,
            model or "default",
            credits_per_operation,
        )
        return self._enrich_with_margin(updated)

    async def delete_price(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str | None = None,
    ) -> bool:
        """Delete a pricing entry.

        Args:
            ai_service: The AI service identifier.
            operation_type: The operation type.

        Returns:
            True if the entry was deleted, False if it did not exist.
        """
        model = normalize_pricing_sub_model(sub_model)
        deleted = await self._pricing_repo.delete(
            ai_service, operation_type, sub_model=model
        )
        if deleted:
            logger.info(
                "Pricing deleted: ai_service=%s, op=%s, model=%s",
                ai_service,
                operation_type,
                model or "default",
            )
        return deleted

    async def delete_all_prices(self, *, ai_service: str | None = None) -> int:
        """Delete all pricing entries, optionally scoped to one provider."""
        count = await self._pricing_repo.delete_all(ai_service=ai_service)
        if count:
            logger.info(
                "Pricing bulk delete: count=%d, ai_service=%s",
                count,
                ai_service or "all",
            )
        return count

    async def sync_from_routing_config(
        self,
        *,
        assignments: dict[str, dict[str, Any]],
        text_fallback_chain: list[dict[str, Any]],
        image_fallback_chain: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create draft pricing rows for routing-required pairs that are missing."""
        from platform_api.services.pricing_sync_service import (
            collect_required_pricing_pairs,
            suggest_pricing_values,
        )

        existing_entries = await self._pricing_repo.get_all()
        existing_keys = {
            pricing_lookup_key(
                str(e["ai_service"]),
                str(e["operation_type"]),
                str(e.get("sub_model") or ""),
            )
            for e in existing_entries
        }

        created: list[dict[str, Any]] = []
        skipped = 0
        for pair in collect_required_pricing_pairs(
            assignments=assignments,
            text_fallback_chain=text_fallback_chain,
            image_fallback_chain=image_fallback_chain,
        ):
            key = pricing_lookup_key(
                pair.ai_service, pair.operation_type, pair.sub_model
            )
            if key in existing_keys:
                skipped += 1
                continue

            credits, cost = suggest_pricing_values(
                ai_service=pair.ai_service,
                operation_type=pair.operation_type,
                sub_model=pair.sub_model,
                existing_entries=existing_entries,
            )
            self._validate_credit_units(credits)
            row = await self._pricing_repo.create(
                pair.ai_service,
                pair.operation_type,
                credits,
                cost,
                sub_model=normalize_pricing_sub_model(pair.sub_model),
                needs_review=True,
            )
            enriched = self._enrich_with_margin(row)
            created.append(enriched)
            existing_entries.append(enriched)
            existing_keys.add(key)
            logger.info(
                "Draft pricing created from routing: %s/%s/%s (%d cr, source=%s)",
                pair.ai_service,
                pair.operation_type,
                normalize_pricing_sub_model(pair.sub_model) or "default",
                credits,
                pair.source,
            )

        return {
            "created_count": len(created),
            "skipped_existing_count": skipped,
            "created": created,
        }

    async def approve_pricing(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str | None = None,
    ) -> dict[str, Any]:
        """Clear needs_review for a pricing row."""
        model = normalize_pricing_sub_model(sub_model)
        existing = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type, model
        )
        if existing is None:
            raise NotFoundError(
                f"No pricing found for ai_service '{ai_service}' "
                f"operation '{operation_type}' model '{model or 'default'}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": model,
                },
            )
        self._validate_pricing_economics(
            operation_type,
            int(existing["credits_per_operation"]),
            existing.get("external_cost_cents"),
        )
        approved = await self._pricing_repo.approve(
            ai_service, operation_type, sub_model=model
        )
        if approved is None:
            raise NotFoundError(
                f"No pricing found for ai_service '{ai_service}' "
                f"operation '{operation_type}' model '{model or 'default'}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": model,
                },
            )
        return self._enrich_with_margin(approved)

    async def approve_pricing_many(
        self, pairs: list[tuple[str, str, str]]
    ) -> dict[str, int]:
        """Approve multiple draft pricing rows."""
        count = await self._pricing_repo.approve_many(pairs)
        return {"approved_count": count}
