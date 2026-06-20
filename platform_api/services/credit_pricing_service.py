"""Credit pricing service for per-model operation pricing configuration.

Provides CRUD operations for credit pricing: configure per-model pricing
(model_identifier + operation_type unique), validate credits_per_operation
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

    async def get_by_model_and_operation(
        self, model_identifier: str, operation_type: str
    ) -> dict[str, Any] | None:
        """Return a pricing entry for a model/operation combination."""
        ...

    async def create(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any]:
        """Create a new pricing entry. Raises on duplicate."""
        ...

    async def update(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any] | None:
        """Update an existing pricing entry. Returns None if not found."""
        ...

    async def delete(
        self, model_identifier: str, operation_type: str
    ) -> bool:
        """Delete a pricing entry. Returns True if deleted, False if not found."""
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

    def __init__(self, pricing_repo: CreditPricingRepositoryProtocol) -> None:
        self._pricing_repo = pricing_repo

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
    # Public API
    # -----------------------------------------------------------------------

    async def get_all_pricing(self) -> list[dict[str, Any]]:
        """Return all configured model pricing with computed margins.

        Requirement 5.4: Returns all configured operations with credit charge,
        external API cost, and calculated margin.

        Returns:
            List of pricing entry dicts with keys: id, model_identifier,
            operation_type, credits_per_operation, external_cost_cents, margin,
            created_at, updated_at.
        """
        entries = await self._pricing_repo.get_all()
        return [self._enrich_with_margin(e) for e in entries]

    async def get_price(self, model_identifier: str, operation_type: str) -> int:
        """Return credits_per_operation for a model/operation combination.

        Requirement 5.6: If no pricing is configured for the requested
        operation, raises ExternalServiceError to reject the generation request.

        Args:
            model_identifier: The AI model identifier (e.g. "suno_v5").
            operation_type: The operation type (e.g. "music_generation").

        Returns:
            The integer credits cost for the operation.

        Raises:
            ExternalServiceError: If no pricing is configured for the
                model/operation combination.
        """
        entry = await self._pricing_repo.get_by_model_and_operation(
            model_identifier, operation_type
        )
        if entry is None:
            raise ExternalServiceError(
                f"No pricing configured for model '{model_identifier}' "
                f"operation '{operation_type}'. This operation is not yet available.",
                details={
                    "model_identifier": model_identifier,
                    "operation_type": operation_type,
                },
            )
        return entry["credits_per_operation"]

    async def set_price(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
    ) -> dict[str, Any]:
        """Create or update pricing for a model/operation combination.

        Requirement 5.1: Store model identifier, operation type,
        credits-per-operation, and external cost.
        Requirement 5.5: Validate credits_per_operation in [1, 10000].
        Requirement 5.7: Enforce unique constraint on (model_identifier, operation_type).

        If the pricing entry already exists, it will be updated (Req 5.2).
        If it does not exist, a new entry is created.

        Args:
            model_identifier: The AI model identifier.
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
        existing = await self._pricing_repo.get_by_model_and_operation(
            model_identifier, operation_type
        )
        if existing is not None:
            updated = await self._pricing_repo.update(
                model_identifier, operation_type, credits_per_operation, external_cost_cents
            )
            if updated is None:
                raise NotFoundError(
                    "Pricing entry not found during update.",
                    details={
                        "model_identifier": model_identifier,
                        "operation_type": operation_type,
                    },
                )
            logger.info(
                "Pricing updated: model=%s, op=%s, credits=%d",
                model_identifier,
                operation_type,
                credits_per_operation,
            )
            return self._enrich_with_margin(updated)

        # Create new entry
        created = await self._pricing_repo.create(
            model_identifier, operation_type, credits_per_operation, external_cost_cents
        )
        logger.info(
            "Pricing created: model=%s, op=%s, credits=%d",
            model_identifier,
            operation_type,
            credits_per_operation,
        )
        return self._enrich_with_margin(created)

    async def create_price(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
    ) -> dict[str, Any]:
        """Create pricing for a model/operation combination (strict create).

        Unlike set_price, this raises DuplicateError if the entry already exists.
        Used by the POST /credits/pricing endpoint (Req 5.7).

        Args:
            model_identifier: The AI model identifier.
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
        existing = await self._pricing_repo.get_by_model_and_operation(
            model_identifier, operation_type
        )
        if existing is not None:
            raise DuplicateError(
                f"Pricing already exists for model '{model_identifier}' "
                f"operation '{operation_type}'.",
                details={
                    "model_identifier": model_identifier,
                    "operation_type": operation_type,
                },
            )

        created = await self._pricing_repo.create(
            model_identifier, operation_type, credits_per_operation, external_cost_cents
        )
        logger.info(
            "Pricing created: model=%s, op=%s, credits=%d",
            model_identifier,
            operation_type,
            credits_per_operation,
        )
        return self._enrich_with_margin(created)

    async def update_price(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
    ) -> dict[str, Any]:
        """Update existing pricing for a model/operation combination (strict update).

        Unlike set_price, this raises NotFoundError if the entry does not exist.
        Used by the PUT /credits/pricing endpoint (Req 5.2).

        Args:
            model_identifier: The AI model identifier.
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

        existing = await self._pricing_repo.get_by_model_and_operation(
            model_identifier, operation_type
        )
        if existing is None:
            raise NotFoundError(
                f"No pricing found for model '{model_identifier}' "
                f"operation '{operation_type}'.",
                details={
                    "model_identifier": model_identifier,
                    "operation_type": operation_type,
                },
            )

        updated = await self._pricing_repo.update(
            model_identifier, operation_type, credits_per_operation, external_cost_cents
        )
        if updated is None:
            raise NotFoundError(
                "Pricing entry not found during update.",
                details={
                    "model_identifier": model_identifier,
                    "operation_type": operation_type,
                },
            )
        logger.info(
            "Pricing updated: model=%s, op=%s, credits=%d",
            model_identifier,
            operation_type,
            credits_per_operation,
        )
        return self._enrich_with_margin(updated)

    async def delete_price(
        self, model_identifier: str, operation_type: str
    ) -> bool:
        """Delete a pricing entry.

        Args:
            model_identifier: The AI model identifier.
            operation_type: The operation type.

        Returns:
            True if the entry was deleted, False if it did not exist.
        """
        deleted = await self._pricing_repo.delete(model_identifier, operation_type)
        if deleted:
            logger.info(
                "Pricing deleted: model=%s, op=%s",
                model_identifier,
                operation_type,
            )
        return deleted
