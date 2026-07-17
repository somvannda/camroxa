"""Admin CRUD for credit packs sold as wallet top-ups."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

from platform_api.services.credit_units import MAX_CREDIT_UNITS, MIN_PACK_CREDIT_UNITS

MIN_PACK_PRICE_CENTS = 50
MAX_PACK_PRICE_CENTS = 10_000_000
MIN_PACK_CREDITS = MIN_PACK_CREDIT_UNITS
MAX_PACK_CREDITS = MAX_CREDIT_UNITS


class CreditPackRepositoryProtocol(Protocol):
    async def get_all_packs(self, *, include_inactive: bool = True) -> list[dict[str, Any]]: ...

    async def get_by_id(self, pack_id: Any) -> dict[str, Any] | None: ...

    async def create_pack(
        self,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int,
        is_active: bool,
    ) -> dict[str, Any]: ...

    async def update_pack(
        self,
        pack_id: Any,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int,
        is_active: bool,
    ) -> dict[str, Any] | None: ...

    async def delete_pack(self, pack_id: Any) -> bool: ...


class CreditPackService:
    """Manage credit packs exposed for wallet top-up purchase."""

    def __init__(self, pack_repo: CreditPackRepositoryProtocol) -> None:
        self._pack_repo = pack_repo

    async def list_packs(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        return await self._pack_repo.get_all_packs(include_inactive=include_inactive)

    async def create_pack(
        self,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValidationError("Pack name is required.", details={"field": "name"})
        self._validate_amounts(price_cents=price_cents, song_credits=song_credits)
        legacy_request_count = (
            int(request_count) if request_count is not None else int(song_credits)
        )
        created = await self._pack_repo.create_pack(
            name=normalized_name,
            price_cents=int(price_cents),
            song_credits=int(song_credits),
            request_count=max(0, legacy_request_count),
            is_active=bool(is_active),
        )
        logger.info(
            "Credit pack created: id=%s name=%s price_cents=%d credits=%d",
            created.get("id"),
            normalized_name,
            price_cents,
            song_credits,
        )
        return created

    async def update_pack(
        self,
        pack_id: str,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int | None = None,
        is_active: bool,
    ) -> dict[str, Any]:
        from uuid import UUID

        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValidationError("Pack name is required.", details={"field": "name"})
        self._validate_amounts(price_cents=price_cents, song_credits=song_credits)
        pack_uuid = UUID(str(pack_id))
        existing = await self._pack_repo.get_by_id(pack_uuid)
        if existing is None:
            raise NotFoundError(
                f"Credit pack '{pack_id}' not found.",
                details={"pack_id": pack_id},
            )
        legacy_request_count = (
            int(request_count)
            if request_count is not None
            else int(existing.get("request_count") or song_credits)
        )
        updated = await self._pack_repo.update_pack(
            pack_uuid,
            name=normalized_name,
            price_cents=int(price_cents),
            song_credits=int(song_credits),
            request_count=max(0, legacy_request_count),
            is_active=bool(is_active),
        )
        if updated is None:
            raise NotFoundError(
                f"Credit pack '{pack_id}' not found.",
                details={"pack_id": pack_id},
            )
        return updated

    async def delete_pack(self, pack_id: str) -> bool:
        from uuid import UUID

        pack_uuid = UUID(str(pack_id))
        deleted = await self._pack_repo.delete_pack(pack_uuid)
        if not deleted:
            raise NotFoundError(
                f"Credit pack '{pack_id}' not found.",
                details={"pack_id": pack_id},
            )
        return True

    @staticmethod
    def _validate_amounts(*, price_cents: int, song_credits: int) -> None:
        if not isinstance(price_cents, int) or price_cents < MIN_PACK_PRICE_CENTS:
            raise ValidationError(
                f"price_cents must be at least {MIN_PACK_PRICE_CENTS}.",
                details={"price_cents": price_cents},
            )
        if price_cents > MAX_PACK_PRICE_CENTS:
            raise ValidationError(
                f"price_cents must not exceed {MAX_PACK_PRICE_CENTS}.",
                details={"price_cents": price_cents},
            )
        if not isinstance(song_credits, int) or song_credits < MIN_PACK_CREDITS:
            raise ValidationError(
                f"song_credits must be at least {MIN_PACK_CREDITS}.",
                details={"song_credits": song_credits},
            )
        if song_credits > MAX_PACK_CREDITS:
            raise ValidationError(
                f"song_credits must not exceed {MAX_PACK_CREDITS}.",
                details={"song_credits": song_credits},
            )
