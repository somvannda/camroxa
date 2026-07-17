"""Repository for admin-managed per-model USD cost estimates."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import asyncpg

from platform_api.exceptions import DuplicateError, NotFoundError
from platform_api.services.money_amounts import normalize_cost_usd


class ModelCostRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
        data = dict(row)
        if "cost_usd" in data and data["cost_usd"] is not None:
            data["cost_usd"] = float(data["cost_usd"])
        return data

    async def get_all(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, ai_service, sub_model, operation_type, cost_usd,
                   notes, source, created_at, updated_at
            FROM ai_model_costs
            ORDER BY ai_service, sub_model, operation_type
            """
        )
        return [self._row_to_dict(row) for row in rows]

    async def get_by_key(
        self,
        ai_service: str,
        sub_model: str,
        operation_type: str,
    ) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, ai_service, sub_model, operation_type, cost_usd,
                   notes, source, created_at, updated_at
            FROM ai_model_costs
            WHERE ai_service = $1 AND sub_model = $2 AND operation_type = $3
            """,
            ai_service,
            sub_model,
            operation_type,
        )
        return self._row_to_dict(row) if row else None

    async def create(
        self,
        *,
        ai_service: str,
        sub_model: str,
        operation_type: str,
        cost_usd: float,
        notes: str | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        amount = normalize_cost_usd(cost_usd)
        try:
            row = await self._pool.fetchrow(
                """
                INSERT INTO ai_model_costs (
                    id, ai_service, sub_model, operation_type,
                    cost_usd, notes, source, created_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), $1, $2, $3, $4, $5, $6, NOW(), NOW()
                )
                RETURNING id, ai_service, sub_model, operation_type, cost_usd,
                          notes, source, created_at, updated_at
                """,
                ai_service,
                sub_model,
                operation_type,
                amount,
                notes,
                source,
            )
        except asyncpg.UniqueViolationError:
            raise DuplicateError(
                "Model cost already exists for this provider/model/operation.",
                details={
                    "ai_service": ai_service,
                    "sub_model": sub_model,
                    "operation_type": operation_type,
                },
            )
        return self._row_to_dict(row)

    async def update(
        self,
        *,
        ai_service: str,
        sub_model: str,
        operation_type: str,
        cost_usd: float,
        notes: str | None = None,
    ) -> dict[str, Any]:
        amount = normalize_cost_usd(cost_usd)
        row = await self._pool.fetchrow(
            """
            UPDATE ai_model_costs
            SET cost_usd = $4,
                notes = $5,
                source = 'manual',
                updated_at = NOW()
            WHERE ai_service = $1 AND sub_model = $2 AND operation_type = $3
            RETURNING id, ai_service, sub_model, operation_type, cost_usd,
                      notes, source, created_at, updated_at
            """,
            ai_service,
            sub_model,
            operation_type,
            amount,
            notes,
        )
        if row is None:
            raise NotFoundError(
                "Model cost entry not found.",
                details={
                    "ai_service": ai_service,
                    "sub_model": sub_model,
                    "operation_type": operation_type,
                },
            )
        return self._row_to_dict(row)

    async def delete(
        self,
        *,
        ai_service: str,
        sub_model: str,
        operation_type: str,
    ) -> bool:
        result = await self._pool.execute(
            """
            DELETE FROM ai_model_costs
            WHERE ai_service = $1 AND sub_model = $2 AND operation_type = $3
            """,
            ai_service,
            sub_model,
            operation_type,
        )
        return "DELETE 1" in result

    async def upsert(
        self,
        *,
        ai_service: str,
        sub_model: str,
        operation_type: str,
        cost_usd: float,
        notes: str | None,
        source: str,
    ) -> dict[str, Any]:
        amount = normalize_cost_usd(cost_usd)
        row = await self._pool.fetchrow(
            """
            INSERT INTO ai_model_costs (
                id, ai_service, sub_model, operation_type,
                cost_usd, notes, source, created_at, updated_at
            )
            VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, NOW(), NOW())
            ON CONFLICT (ai_service, sub_model, operation_type)
            DO UPDATE SET
                cost_usd = EXCLUDED.cost_usd,
                notes = COALESCE(EXCLUDED.notes, ai_model_costs.notes),
                source = EXCLUDED.source,
                updated_at = NOW()
            RETURNING id, ai_service, sub_model, operation_type, cost_usd,
                      notes, source, created_at, updated_at
            """,
            ai_service,
            sub_model,
            operation_type,
            amount,
            notes,
            source,
        )
        return self._row_to_dict(row)
