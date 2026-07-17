"""Service for admin CRUD on per-model USD cost estimates."""

from __future__ import annotations

from typing import Any, Protocol

from platform_api.exceptions import ValidationError
from platform_api.services.model_cost_estimates import build_seed_cost_rows
from platform_api.services.money_amounts import normalize_cost_usd
from platform_api.services.pricing_keys import normalize_pricing_sub_model


class ModelCostRepositoryProtocol(Protocol):
    async def get_all(self) -> list[dict[str, Any]]: ...

    async def create(
        self,
        *,
        ai_service: str,
        sub_model: str,
        operation_type: str,
        cost_usd: float,
        notes: str | None = None,
        source: str = "manual",
    ) -> dict[str, Any]: ...

    async def update(
        self,
        *,
        ai_service: str,
        sub_model: str,
        operation_type: str,
        cost_usd: float,
        notes: str | None = None,
    ) -> dict[str, Any]: ...

    async def delete(
        self, *, ai_service: str, sub_model: str, operation_type: str
    ) -> bool: ...

    async def upsert(
        self,
        *,
        ai_service: str,
        sub_model: str,
        operation_type: str,
        cost_usd: float,
        notes: str | None,
        source: str,
    ) -> dict[str, Any]: ...


class ModelCostService:
    def __init__(self, repo: ModelCostRepositoryProtocol) -> None:
        self._repo = repo

    async def list_costs(self) -> list[dict[str, Any]]:
        return await self._repo.get_all()

    async def create_cost(
        self,
        *,
        ai_service: str,
        operation_type: str,
        cost_usd: float,
        sub_model: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        self._validate_cost(cost_usd)
        return await self._repo.create(
            ai_service=ai_service.strip(),
            sub_model=normalize_pricing_sub_model(sub_model),
            operation_type=operation_type.strip(),
            cost_usd=float(normalize_cost_usd(cost_usd)),
            notes=notes,
            source="manual",
        )

    async def update_cost(
        self,
        *,
        ai_service: str,
        operation_type: str,
        cost_usd: float,
        sub_model: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        self._validate_cost(cost_usd)
        return await self._repo.update(
            ai_service=ai_service.strip(),
            sub_model=normalize_pricing_sub_model(sub_model),
            operation_type=operation_type.strip(),
            cost_usd=float(normalize_cost_usd(cost_usd)),
            notes=notes,
        )

    async def delete_cost(
        self,
        *,
        ai_service: str,
        operation_type: str,
        sub_model: str | None = None,
    ) -> bool:
        return await self._repo.delete(
            ai_service=ai_service.strip(),
            sub_model=normalize_pricing_sub_model(sub_model),
            operation_type=operation_type.strip(),
        )

    async def seed_from_registry(self, *, overwrite: bool = False) -> dict[str, int]:
        """Populate model costs from registry estimates where possible."""
        seed_rows = build_seed_cost_rows()
        valid_keys = {
            (row["ai_service"], row["sub_model"], row["operation_type"]) for row in seed_rows
        }
        existing = {
            (
                str(row["ai_service"]),
                normalize_pricing_sub_model(row.get("sub_model")),
                str(row["operation_type"]),
            )
            for row in await self._repo.get_all()
        }

        created = 0
        skipped = 0
        pruned = 0
        for row in await self._repo.get_all():
            if str(row.get("source") or "") != "registry":
                continue
            key = (
                str(row["ai_service"]),
                normalize_pricing_sub_model(row.get("sub_model")),
                str(row["operation_type"]),
            )
            if key not in valid_keys:
                if await self._repo.delete(
                    ai_service=key[0],
                    sub_model=key[1],
                    operation_type=key[2],
                ):
                    pruned += 1
                existing.discard(key)

        for row in seed_rows:
            key = (row["ai_service"], row["sub_model"], row["operation_type"])
            if key in existing and not overwrite:
                skipped += 1
                continue
            await self._repo.upsert(
                ai_service=row["ai_service"],
                sub_model=row["sub_model"],
                operation_type=row["operation_type"],
                cost_usd=float(row["cost_usd"]),
                notes=row.get("notes"),
                source=str(row.get("source") or "registry"),
            )
            created += 1
            existing.add(key)

        return {
            "seeded_count": created,
            "skipped_existing_count": skipped,
            "pruned_count": pruned,
        }

    @staticmethod
    def _validate_cost(cost_usd: float) -> None:
        if float(normalize_cost_usd(cost_usd)) < 0:
            raise ValidationError(
                "cost_usd must be >= 0.",
                details={"cost_usd": cost_usd},
            )
