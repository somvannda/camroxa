"""Royalty policy versions and defaults.

This service was referenced by ``routers/streaming_admin.py`` before it existed,
which made the admin streaming catalog fail on import. It now owns:

- the default policy document used until an admin publishes one;
- deep-merging partial documents so older rows keep working;
- creating immutable, versioned policy documents.

Money is expressed in **micro-USD** (1e-6 USD), matching ``royalty_math``.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

from platform_api.exceptions import ValidationError

# Conservative launch defaults. Finance must approve the pool size before the
# first payout; the service falls back to this document when no row exists.
DEFAULT_ROYALTY_POLICY: dict[str, Any] = {
    "version": 1,
    "currency": "USD",
    "period": "monthly",
    "pool": {
        "mode": "fixed",
        "amount_usd": 3000,
        "revenue_share_pct": 15,
        "floor_usd": 3000,
        "cap_pct_gross": 25,
    },
    "eligibility_streams": 500,
    "eligibility_unique_listeners": 50,
    "eligibility": {
        "min_valid_streams": 500,
        "min_unique_listeners": 50,
        "min_account_age_days": 30,
    },
    "weights": {
        "original": 1.0,
        "ai_assisted": 0.6,
        "ai_generated": 0.3,
    },
    "caps": {
        "per_track_weighted_streams": 500_000,
        "per_creator_pool_pct": 40,
    },
    # Compatibility keys still read by the existing admin catalog.
    "ai": {"max_royalty_streams": 500_000},
    "original": {"max_royalty_streams": 500_000},
    "holdback_days": 30,
    "new_creator_holdback_days": 90,
    "reserve_pct": 10,
    "min_payout_usd": 20,
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``."""
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def normalize_policy(document: dict[str, Any] | None) -> dict[str, Any]:
    """Merge defaults and keep the legacy compatibility keys in sync."""
    source = document or {}
    merged = _merge(DEFAULT_ROYALTY_POLICY, source)

    source_eligibility = source.get("eligibility") or {}
    eligibility = merged.setdefault("eligibility", {})
    if source.get("eligibility_streams") is not None:
        min_streams = int(source["eligibility_streams"])
    elif source_eligibility.get("min_valid_streams") is not None:
        min_streams = int(source_eligibility["min_valid_streams"])
    else:
        min_streams = int(eligibility.get("min_valid_streams") or 500)

    if source.get("eligibility_unique_listeners") is not None:
        min_listeners = int(source["eligibility_unique_listeners"])
    elif source_eligibility.get("min_unique_listeners") is not None:
        min_listeners = int(source_eligibility["min_unique_listeners"])
    else:
        min_listeners = int(eligibility.get("min_unique_listeners") or 50)

    eligibility["min_valid_streams"] = min_streams
    eligibility["min_unique_listeners"] = min_listeners
    eligibility.setdefault("min_account_age_days", 30)
    merged["eligibility_streams"] = min_streams
    merged["eligibility_unique_listeners"] = min_listeners

    caps = merged.setdefault("caps", {})
    track_cap = int(caps.get("per_track_weighted_streams") or 500_000)
    caps["per_track_weighted_streams"] = track_cap
    caps["per_creator_pool_pct"] = float(caps.get("per_creator_pool_pct") or 40)

    source_ai = source.get("ai") or {}
    source_original = source.get("original") or {}
    merged.setdefault("ai", {})
    merged["ai"]["max_royalty_streams"] = int(
        source_ai.get("max_royalty_streams") or track_cap
    )
    merged.setdefault("original", {})
    merged["original"]["max_royalty_streams"] = int(
        source_original.get("max_royalty_streams") or track_cap
    )

    weights = merged.setdefault("weights", {})
    for key, default in (("original", 1.0), ("ai_assisted", 0.6), ("ai_generated", 0.3)):
        weights[key] = float(weights.get(key, default))

    return merged


def validate_policy(document: dict[str, Any]) -> None:
    """Raise ``ValidationError`` when a policy is unsafe or impossible."""
    errors: dict[str, str] = {}

    pool = document.get("pool") or {}
    for key in ("amount_usd", "floor_usd"):
        value = pool.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            errors[f"pool.{key}"] = "must be a non-negative number"
    if not 0 <= float(pool.get("revenue_share_pct") or 0) <= 100:
        errors["pool.revenue_share_pct"] = "must be between 0 and 100"
    if not 0 <= float(pool.get("cap_pct_gross") or 0) <= 100:
        errors["pool.cap_pct_gross"] = "must be between 0 and 100"

    weights = document.get("weights") or {}
    for key in ("original", "ai_assisted", "ai_generated"):
        value = weights.get(key)
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            errors[f"weights.{key}"] = "must be between 0 and 1"

    caps = document.get("caps") or {}
    track_cap = caps.get("per_track_weighted_streams")
    if not isinstance(track_cap, int) or track_cap <= 0:
        errors["caps.per_track_weighted_streams"] = "must be a positive integer"
    creator_cap = caps.get("per_creator_pool_pct")
    if not isinstance(creator_cap, (int, float)) or not 0 < float(creator_cap) <= 100:
        errors["caps.per_creator_pool_pct"] = "must be between 0 and 100"

    for key in ("holdback_days", "new_creator_holdback_days"):
        value = document.get(key)
        if not isinstance(value, int) or value < 0:
            errors[key] = "must be a non-negative integer"
    reserve = document.get("reserve_pct")
    if not isinstance(reserve, (int, float)) or not 0 <= float(reserve) <= 100:
        errors["reserve_pct"] = "must be between 0 and 100"
    if not isinstance(document.get("min_payout_usd"), (int, float)) or document["min_payout_usd"] < 0:
        errors["min_payout_usd"] = "must be a non-negative number"

    if errors:
        raise ValidationError("Invalid royalty policy.", details={"fields": errors})


def _row_to_policy(row: Any) -> dict[str, Any]:
    document = row["document"]
    if isinstance(document, str):
        document = json.loads(document)
    return {
        "id": row["id"],
        "version": int(row["version"]),
        "document": normalize_policy(document),
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"],
        "created_at": row["created_at"],
        "source": "database",
    }


class RoyaltyPolicyService:
    """Reads the active policy and creates new immutable versions."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def get_active(self) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT id, version, document, effective_from, effective_to, created_at
            FROM royalty_policies
            WHERE effective_from <= NOW()
              AND (effective_to IS NULL OR effective_to > NOW())
            ORDER BY effective_from DESC, version DESC
            LIMIT 1
            """
        )
        if row is None:
            return {
                "id": None,
                "version": 0,
                "document": normalize_policy(None),
                "effective_from": None,
                "effective_to": None,
                "created_at": None,
                "source": "default",
            }
        return _row_to_policy(row)

    async def get_by_version(self, version: int) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, version, document, effective_from, effective_to, created_at
            FROM royalty_policies
            WHERE version = $1
            """,
            version,
        )
        return _row_to_policy(row) if row else None

    async def list_versions(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, version, document, effective_from, effective_to, created_at
            FROM royalty_policies
            ORDER BY version DESC
            LIMIT $1
            """,
            max(1, min(limit, 100)),
        )
        return [_row_to_policy(row) for row in rows]

    async def create_version(
        self,
        document: dict[str, Any],
        *,
        effective_from: datetime | None = None,
        created_by: Any = None,
    ) -> dict[str, Any]:
        normalized = normalize_policy(document)
        validate_policy(normalized)
        starts_at = effective_from or datetime.now(timezone.utc)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchval(
                    "SELECT COALESCE(MAX(version), 0) FROM royalty_policies"
                )
                next_version = int(current or 0) + 1
                await conn.execute(
                    """
                    UPDATE royalty_policies
                    SET effective_to = $1
                    WHERE effective_to IS NULL
                      AND effective_from <= $1
                    """,
                    starts_at,
                )
                row = await conn.fetchrow(
                    """
                    INSERT INTO royalty_policies (version, document, effective_from, created_by)
                    VALUES ($1, $2::jsonb, $3, $4)
                    RETURNING id, version, document, effective_from, effective_to, created_at
                    """,
                    next_version,
                    json.dumps(normalized),
                    starts_at,
                    created_by,
                )
        return _row_to_policy(row)
