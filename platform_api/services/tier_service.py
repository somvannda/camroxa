"""Free / Pro tier — derived from live credit pack lots.

Tier is never stored. It is a read-time projection:

    Pro  <=> EXISTS(live pack lot)          # remaining_units > 0 and not expired
    Free <=> otherwise

This keeps expiry, refunds and purchases consistent without a sync job.
See docs/credits-only-two-tier.md (R1-R5).
"""

from __future__ import annotations

from typing import Any, Iterable
from uuid import UUID

TIER_FREE = "free"
TIER_PRO = "pro"

_IS_PRO_SQL = """
SELECT EXISTS (
    SELECT 1
    FROM credit_wallet_lots
    WHERE user_id = $1
      AND tag = 'pack'
      AND remaining_units > 0
      AND (expires_at IS NULL OR expires_at > now())
)
"""

_TIERS_SQL = """
SELECT u.uid,
       EXISTS (
           SELECT 1
           FROM credit_wallet_lots l
           WHERE l.user_id = u.uid
             AND l.tag = 'pack'
             AND l.remaining_units > 0
             AND (l.expires_at IS NULL OR l.expires_at > now())
       ) AS is_pro
FROM unnest($1::uuid[]) AS u(uid)
"""


def _as_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


async def is_pro(pool: Any, user_id: UUID | str) -> bool:
    """True when the user has at least one live pack lot."""
    return bool(await pool.fetchval(_IS_PRO_SQL, _as_uuid(user_id)))


async def get_tier(pool: Any, user_id: UUID | str) -> str:
    return TIER_PRO if await is_pro(pool, user_id) else TIER_FREE


async def tiers_for(pool: Any, user_ids: Iterable[UUID | str]) -> dict[str, str]:
    """Batch variant for admin lists. Returns {user_id: 'free'|'pro'}."""
    ids = [_as_uuid(value) for value in user_ids]
    if not ids:
        return {}
    rows = await pool.fetch(_TIERS_SQL, ids)
    return {
        str(row["uid"]): TIER_PRO if row["is_pro"] else TIER_FREE for row in rows
    }


def tier_sql(alias: str = "w") -> str:
    """SQL fragment usable in a SELECT over credit_wallets (alias must have user_id)."""
    return f"""
    CASE WHEN EXISTS (
        SELECT 1
        FROM credit_wallet_lots tier_lot
        WHERE tier_lot.user_id = {alias}.user_id
          AND tier_lot.tag = 'pack'
          AND tier_lot.remaining_units > 0
          AND (tier_lot.expires_at IS NULL OR tier_lot.expires_at > now())
    ) THEN '{TIER_PRO}' ELSE '{TIER_FREE}' END
    """
