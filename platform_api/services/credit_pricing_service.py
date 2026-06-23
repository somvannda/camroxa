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

logger = logging.getLogger(__name__)

# Pricing bounds per Requirement 5.5
MIN_CREDITS_PER_OPERATION = 1
MAX_CREDITS_PER_OPERATION = 10_000


# ---------------------------------------------------------------------------
# Protocol interfaces for dependency injection
# ---------------------------------------------------------------------------


class CreditPricingRepositoryProtocol(Protocol):
    """Protocol for credit pricing repository operations."""

    async def get_all(self) -> list[dict[str, Any]]:
        """Return all configured pricing entries."""
        ...

    async def get_by_service_and_operation(
        self, ai_service: str, operation_type: str
    ) -> dict[str, Any] | None:
        """Return a pricing entry for an ai_service/operation combination."""
        ...

    async def create(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any]:
        """Create a new pricing entry. Raises on duplicate."""
        ...

    async def update(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any] | None:
        """Update an existing pricing entry. Returns None if not found."""
        ...

    async def delete(
        self, ai_service: str, operation_type: str
    ) -> bool:
        """Delete a pricing entry. Returns True if deleted, False if not found."""
        ...


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
        """Compute profit margin: credits_per_operation - (external_cost_cents / 100).

        Returns None if external_cost_cents is not set.
        """
        if external_cost_cents is None:
            return None
        return credits_per_operation - (external_cost_cents / 100)

    def _validate_credits(self, credits_per_operation: int) -> None:
        """Validate credits_per_operation is within [1, 10000].

        Requirement 5.5: Credit prices must be integers >= 1 and <= 10000.

        Raises:
            ValidationError: If value is outside acceptable range or not an integer.
        """
        if not isinstance(credits_per_operation, int):
            raise ValidationError(
                "credits_per_operation must be an integer.",
                details={"credits_per_operation": credits_per_operation},
            )
        if credits_per_operation < MIN_CREDITS_PER_OPERATION:
            raise ValidationError(
                f"credits_per_operation must be at least {MIN_CREDITS_PER_OPERATION}.",
                details={
                    "credits_per_operation": credits_per_operation,
                    "min": MIN_CREDITS_PER_OPERATION,
                    "max": MAX_CREDITS_PER_OPERATION,
                },
            )
        if credits_per_operation > MAX_CREDITS_PER_OPERATION:
            raise ValidationError(
                f"credits_per_operation must not exceed {MAX_CREDITS_PER_OPERATION}.",
                details={
                    "credits_per_operation": credits_per_operation,
                    "min": MIN_CREDITS_PER_OPERATION,
                    "max": MAX_CREDITS_PER_OPERATION,
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
        sell_price_cents = round(credits_per_operation * global_credit_value * 100)
        profit_margin_cents = sell_price_cents - external_cost_cents
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

    async def get_price(self, ai_service: str, operation_type: str) -> int:
        """Return credits_per_operation for an ai_service/operation combination.

        Requirement 5.6: If no pricing is configured for the requested
        operation, raises ExternalServiceError to reject the generation request.

        Args:
            ai_service: The AI service identifier (e.g. "suno").
            operation_type: The operation type (e.g. "music_generation").

        Returns:
            The integer credits cost for the operation.

        Raises:
            ExternalServiceError: If no pricing is configured for the
                ai_service/operation combination.
        """
        entry = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type
        )
        if entry is None:
            raise ExternalServiceError(
                f"No pricing configured for ai_service '{ai_service}' "
                f"operation '{operation_type}'. This operation is not yet available.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                },
            )
        return entry["credits_per_operation"]

    async def set_price(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
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
        self._validate_credits(credits_per_operation)

        # Try to update existing entry first
        existing = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type
        )
        if existing is not None:
            updated = await self._pricing_repo.update(
                ai_service, operation_type, credits_per_operation, external_cost_cents
            )
            if updated is None:
                raise NotFoundError(
                    "Pricing entry not found during update.",
                    details={
                        "ai_service": ai_service,
                        "operation_type": operation_type,
                    },
                )
            logger.info(
                "Pricing updated: ai_service=%s, op=%s, credits=%d",
                ai_service,
                operation_type,
                credits_per_operation,
            )
            return self._enrich_with_margin(updated)

        # Create new entry
        created = await self._pricing_repo.create(
            ai_service, operation_type, credits_per_operation, external_cost_cents
        )
        logger.info(
            "Pricing created: ai_service=%s, op=%s, credits=%d",
            ai_service,
            operation_type,
            credits_per_operation,
        )
        return self._enrich_with_margin(created)

    async def create_price(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
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
        self._validate_credits(credits_per_operation)

        # Check for existing entry
        existing = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type
        )
        if existing is not None:
            raise DuplicateError(
                f"Pricing already exists for ai_service '{ai_service}' "
                f"operation '{operation_type}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                },
            )

        created = await self._pricing_repo.create(
            ai_service, operation_type, credits_per_operation, external_cost_cents
        )
        logger.info(
            "Pricing created: ai_service=%s, op=%s, credits=%d",
            ai_service,
            operation_type,
            credits_per_operation,
        )
        return self._enrich_with_margin(created)

    async def update_price(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
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
        self._validate_credits(credits_per_operation)

        existing = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type
        )
        if existing is None:
            raise NotFoundError(
                f"No pricing found for ai_service '{ai_service}' "
                f"operation '{operation_type}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                },
            )

        updated = await self._pricing_repo.update(
            ai_service, operation_type, credits_per_operation, external_cost_cents
        )
        if updated is None:
            raise NotFoundError(
                "Pricing entry not found during update.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                },
            )
        logger.info(
            "Pricing updated: ai_service=%s, op=%s, credits=%d",
            ai_service,
            operation_type,
            credits_per_operation,
        )
        return self._enrich_with_margin(updated)

    async def delete_price(
        self, ai_service: str, operation_type: str
    ) -> bool:
        """Delete a pricing entry.

        Args:
            ai_service: The AI service identifier.
            operation_type: The operation type.

        Returns:
            True if the entry was deleted, False if it did not exist.
        """
        deleted = await self._pricing_repo.delete(ai_service, operation_type)
        if deleted:
            logger.info(
                "Pricing deleted: ai_service=%s, op=%s",
                ai_service,
                operation_type,
            )
        return deleted
