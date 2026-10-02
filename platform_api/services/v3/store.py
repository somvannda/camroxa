"""SQL helpers for v3-only columns/tables. Uses the same DB as v1."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from platform_api.services.billing_calendar import billing_usage_date

V3_PLAN_SELECT = """
    id, name, price_cents, billing_cycle_days, profile_allowance,
    monthly_song_limit, monthly_credits, daily_credits, is_public, is_active,
    plan_kind, plan_type, lyric_credits, title_credits, album_credits,
    music_credits, style_credits, image_credits, video_credits, merge_credits,
    pricing_features, pricing_credit_lines, created_at, updated_at
"""


def row_to_plan_dict(
    row: Any,
    *,
    public: bool = False,
    credits_per_generate: int | float | None = None,
) -> dict[str, Any]:
    from platform_api.services.pricing_display import (
        normalize_pricing_features,
        resolve_pricing_credit_lines,
        resolve_pricing_features,
    )

    name = row["name"]
    price_cents = int(row["price_cents"] or 0)
    daily_credits = int(row["daily_credits"] or 0) if row.get("daily_credits") is not None else 0
    monthly_credits = int(row["monthly_credits"] or 0) if row.get("monthly_credits") is not None else 0
    pricing_features = normalize_pricing_features(row.get("pricing_features"))
    pricing_credit_lines = normalize_pricing_features(row.get("pricing_credit_lines"))
    if public:
        pricing_features = resolve_pricing_features(
            pricing_features,
            name=str(name or ""),
            price_cents=price_cents,
            daily_credits=daily_credits,
            monthly_credits=monthly_credits,
        )
        pricing_credit_lines = resolve_pricing_credit_lines(
            pricing_credit_lines,
            monthly_credits=monthly_credits,
            daily_credits=daily_credits,
            credits_per_generate=credits_per_generate,
        )
    return {
        "id": str(row["id"]),
        "name": name,
        "price_cents": price_cents,
        "billing_cycle_days": row.get("billing_cycle_days"),
        "profile_allowance": int(row["profile_allowance"] or 0),
        "monthly_song_limit": row.get("monthly_song_limit"),
        "monthly_credits": monthly_credits,
        "daily_credits": daily_credits,
        "is_public": bool(row.get("is_public")),
        "is_active": bool(row["is_active"]),
        "plan_kind": str(row.get("plan_kind") or "subscription"),
        "plan_type": str(row.get("plan_type") or "desktop_pro"),
        "lyric_credits": row.get("lyric_credits"),
        "title_credits": row.get("title_credits"),
        "album_credits": row.get("album_credits"),
        "music_credits": row.get("music_credits"),
        "style_credits": row.get("style_credits"),
        "image_credits": row.get("image_credits"),
        "video_credits": row.get("video_credits"),
        "merge_credits": row.get("merge_credits"),
        "pricing_features": pricing_features,
        "pricing_credit_lines": pricing_credit_lines,
        "credits_per_generate": credits_per_generate,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class V3BillingStore:
    """Reads/writes additive v3 columns on the shared plans/wallet tables."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def list_plans(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            f"""
            SELECT {V3_PLAN_SELECT}
            FROM plans
            ORDER BY plan_kind ASC, price_cents ASC, name ASC
            """
        )
        return [row_to_plan_dict(row) for row in rows]

    async def list_public_plans(
        self,
        *,
        credits_per_generate: int | float | None = None,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            f"""
            SELECT {V3_PLAN_SELECT}
            FROM plans
            WHERE is_active = true AND is_public = true
            ORDER BY display_order ASC NULLS LAST, price_cents ASC, name ASC
            """
        )
        return [
            row_to_plan_dict(row, public=True, credits_per_generate=credits_per_generate)
            for row in rows
        ]

    async def get_plan(self, plan_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            f"SELECT {V3_PLAN_SELECT} FROM plans WHERE id = $1",
            plan_id,
        )
        return row_to_plan_dict(row) if row is not None else None

    async def get_plan_for_user(self, user_id: UUID) -> dict[str, Any] | None:
        qualified = ", ".join(
            f"p.{part.strip()}" for part in V3_PLAN_SELECT.split(",") if part.strip()
        )
        row = await self._pool.fetchrow(
            f"""
            SELECT {qualified}
            FROM plans p
            INNER JOIN licenses l ON l.plan_id = p.id
            WHERE l.user_id = $1
              AND l.status = 'active'
              AND (l.expires_at IS NULL OR l.expires_at > NOW())
            ORDER BY l.activated_at DESC
            LIMIT 1
            """,
            user_id,
        )
        return row_to_plan_dict(row) if row is not None else None

    async def get_plan_for_web_subscription(self, user_id: UUID) -> dict[str, Any] | None:
        qualified = ", ".join(
            f"p.{part.strip()}" for part in V3_PLAN_SELECT.split(",") if part.strip()
        )
        row = await self._pool.fetchrow(
            f"""
            SELECT {qualified}
            FROM plans p
            INNER JOIN web_subscriptions ws ON ws.plan_id = p.id
            WHERE ws.user_id = $1
              AND ws.status = 'active'
              AND ws.current_period_end > NOW()
            ORDER BY ws.current_period_end DESC
            LIMIT 1
            """,
            user_id,
        )
        return row_to_plan_dict(row) if row is not None else None

    async def get_active_free_plan(self) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            f"""
            SELECT {V3_PLAN_SELECT}
            FROM plans
            WHERE lower(name) = 'free'
              AND is_active = true
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        return row_to_plan_dict(row) if row is not None else None

    async def resolve_charge_plan(self, user_id: UUID) -> dict[str, Any] | None:
        plan = await self.get_plan_for_user(user_id)
        if plan is not None:
            return plan
        web_plan = await self.get_plan_for_web_subscription(user_id)
        if web_plan is not None and int(web_plan.get("price_cents") or 0) > 0:
            return web_plan
        return await self.get_active_free_plan()

    async def patch_plan(self, plan_id: UUID, fields: dict[str, Any]) -> dict[str, Any] | None:
        if not fields:
            return await self.get_plan(plan_id)
        set_parts: list[str] = []
        values: list[Any] = []
        idx = 1
        for col, val in fields.items():
            set_parts.append(f"{col} = ${idx}")
            values.append(val)
            idx += 1
        set_parts.append(f"updated_at = ${idx}")
        values.append(datetime.now(timezone.utc))
        idx += 1
        values.append(plan_id)
        row = await self._pool.fetchrow(
            f"""
            UPDATE plans
            SET {', '.join(set_parts)}
            WHERE id = ${idx}
            RETURNING {V3_PLAN_SELECT}
            """,
            *values,
        )
        return row_to_plan_dict(row) if row is not None else None

    async def list_lots(self, user_id: UUID) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, user_id, tag, amount_units, remaining_units, expires_at,
                   period_start, created_at
            FROM credit_wallet_lots
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [dict(row) for row in rows]

    async def grant_remaining_units(self, user_id: UUID) -> int:
        value = await self._pool.fetchval(
            """
            SELECT COALESCE(SUM(remaining_units), 0)
            FROM credit_wallet_lots
            WHERE user_id = $1
              AND tag IN ('grant', 'daily_grant')
              AND remaining_units > 0
              AND (expires_at IS NULL OR expires_at > NOW())
            """,
            user_id,
        )
        return int(value or 0)

    async def insert_lot(
        self,
        *,
        user_id: UUID,
        tag: str,
        amount_units: int,
        expires_at: datetime | None,
        period_start: date | None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            INSERT INTO credit_wallet_lots (
                id, user_id, tag, amount_units, remaining_units,
                expires_at, period_start, created_at
            )
            VALUES ($1, $2, $3, $4, $4, $5, $6, NOW())
            RETURNING id, user_id, tag, amount_units, remaining_units,
                      expires_at, period_start, created_at
            """,
            uuid4(),
            user_id,
            tag,
            amount_units,
            expires_at,
            period_start,
        )
        return dict(row)

    async def insert_lot_if_absent(
        self,
        *,
        user_id: UUID,
        tag: str,
        amount_units: int,
        expires_at: datetime | None,
        period_start: date | None,
    ) -> dict[str, Any] | None:
        """Insert a grant lot, or return None if the unique (user, period) lot exists.

        Call this *before* add_credits. A rejected lot must not leave a wallet credit.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO credit_wallet_lots (
                id, user_id, tag, amount_units, remaining_units,
                expires_at, period_start, created_at
            )
            VALUES ($1, $2, $3, $4, $4, $5, $6, NOW())
            ON CONFLICT DO NOTHING
            RETURNING id, user_id, tag, amount_units, remaining_units,
                      expires_at, period_start, created_at
            """,
            uuid4(),
            user_id,
            tag,
            amount_units,
            expires_at,
            period_start,
        )
        return dict(row) if row is not None else None

    async def find_period_grant(self, user_id: UUID, period_start: date) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, remaining_units, amount_units, expires_at
            FROM credit_wallet_lots
            WHERE user_id = $1 AND tag = 'grant' AND period_start = $2
            """,
            user_id,
            period_start,
        )
        return dict(row) if row is not None else None

    async def top_up_period_grant(
        self,
        lot_id: UUID,
        *,
        target_units: int,
        expires_at: datetime,
    ) -> int:
        """Raise a period-grant lot to ``target_units``; return the units added.

        Used when a user's plan changes mid-period (e.g. Free -> paid on the same
        day) so the already-minted smaller lot grows to the new plan's grant
        instead of being skipped. Row-locked, so concurrent callers cannot
        double-credit: the loser sees ``amount_units >= target_units`` and gets 0.
        """
        row = await self._pool.fetchrow(
            """
            WITH current AS (
                SELECT id, amount_units
                FROM credit_wallet_lots
                WHERE id = $1
                FOR UPDATE
            )
            UPDATE credit_wallet_lots l
            SET amount_units = $2,
                remaining_units = l.remaining_units + ($2 - current.amount_units),
                expires_at = $3
            FROM current
            WHERE l.id = current.id AND current.amount_units < $2
            RETURNING ($2 - current.amount_units) AS delta_units
            """,
            lot_id,
            target_units,
            expires_at,
        )
        return int(row["delta_units"]) if row is not None else 0

    async def get_web_subscription_period_start(self, user_id: UUID) -> date | None:
        """Billing-period start of the user's active web (CutLuy) subscription."""
        row = await self._pool.fetchrow(
            """
            SELECT current_period_start
            FROM web_subscriptions
            WHERE user_id = $1
              AND status = 'active'
              AND current_period_end > NOW()
            ORDER BY current_period_end DESC
            LIMIT 1
            """,
            user_id,
        )
        if row is None or row["current_period_start"] is None:
            return None
        return billing_usage_date(row["current_period_start"])

    async def find_daily_grant(self, user_id: UUID, period_start: date) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, remaining_units, amount_units, expires_at
            FROM credit_wallet_lots
            WHERE user_id = $1 AND tag = 'daily_grant' AND period_start = $2
            """,
            user_id,
            period_start,
        )
        return dict(row) if row is not None else None

    async def expired_grant_lots(self, user_id: UUID | None = None) -> list[dict[str, Any]]:
        if user_id is None:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, remaining_units
                FROM credit_wallet_lots
                WHERE tag IN ('grant', 'daily_grant')
                  AND remaining_units > 0
                  AND expires_at IS NOT NULL
                  AND expires_at <= NOW()
                """
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, remaining_units
                FROM credit_wallet_lots
                WHERE user_id = $1
                  AND tag IN ('grant', 'daily_grant')
                  AND remaining_units > 0
                  AND expires_at IS NOT NULL
                  AND expires_at <= NOW()
                """,
                user_id,
            )
        return [dict(row) for row in rows]

    async def zero_lot_remaining(self, lot_id: UUID) -> None:
        await self._pool.execute(
            "UPDATE credit_wallet_lots SET remaining_units = 0 WHERE id = $1",
            lot_id,
        )

    async def get_applied_conversion(self, user_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, leftover_packages, credits_minted, amount_units, status
            FROM billing_conversion_runs
            WHERE user_id = $1 AND status = 'applied'
            """,
            user_id,
        )
        return dict(row) if row is not None else None

    async def insert_conversion_run(
        self,
        *,
        user_id: UUID,
        plan_id: UUID | None,
        leftover_packages: int,
        credits_minted: int,
        amount_units: int,
        status: str,
        dry_run: bool,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            INSERT INTO billing_conversion_runs (
                id, user_id, plan_id, leftover_packages, credits_minted,
                amount_units, status, dry_run, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            RETURNING id, user_id, leftover_packages, credits_minted, status, dry_run
            """,
            uuid4(),
            user_id,
            plan_id,
            leftover_packages,
            credits_minted,
            amount_units,
            status,
            dry_run,
        )
        return dict(row)

    async def list_active_license_users(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT DISTINCT ON (l.user_id)
                   l.user_id, l.id AS license_id, l.expires_at,
                   p.id AS plan_id, p.name AS plan_name,
                   p.price_cents, p.monthly_song_limit, p.billing_cycle_days
            FROM licenses l
            INNER JOIN plans p ON p.id = l.plan_id
            WHERE l.user_id IS NOT NULL
              AND l.status = 'active'
              AND (l.expires_at IS NULL OR l.expires_at > NOW())
            ORDER BY l.user_id, l.activated_at DESC
            """
        )
        return [dict(row) for row in rows]

    async def has_transaction_ref(self, ref_id: str) -> bool:
        value = await self._pool.fetchval(
            "SELECT 1 FROM credit_transactions WHERE ref_id = $1 LIMIT 1",
            ref_id,
        )
        return value is not None

    async def list_active_web_subscribers(
        self,
        user_ids: list[UUID] | None = None,
    ) -> list[dict[str, Any]]:
        if user_ids:
            rows = await self._pool.fetch(
                """
                SELECT
                    ws.user_id, ws.id AS subscription_id, ws.plan_id,
                    ws.monthly_credits_granted, ws.monthly_credits_used,
                    ws.topup_credits_balance, ws.status, ws.current_period_end,
                    p.name AS plan_name, p.price_cents
                FROM web_subscriptions ws
                INNER JOIN plans p ON p.id = ws.plan_id
                WHERE ws.status = 'active'
                  AND ws.current_period_end > NOW()
                  AND ws.user_id = ANY($1::uuid[])
                ORDER BY ws.current_period_end DESC
                """,
                user_ids,
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT
                    ws.user_id, ws.id AS subscription_id, ws.plan_id,
                    ws.monthly_credits_granted, ws.monthly_credits_used,
                    ws.topup_credits_balance, ws.status, ws.current_period_end,
                    p.name AS plan_name, p.price_cents
                FROM web_subscriptions ws
                INNER JOIN plans p ON p.id = ws.plan_id
                WHERE ws.status = 'active'
                  AND ws.current_period_end > NOW()
                ORDER BY ws.current_period_end DESC
                """
            )
        return [dict(row) for row in rows]

    async def zero_web_monthly_remaining(self, user_id: UUID) -> None:
        await self._pool.execute(
            """
            UPDATE web_subscriptions
            SET monthly_credits_used = monthly_credits_granted
            WHERE user_id = $1
              AND status = 'active'
            """,
            user_id,
        )

    async def subtract_web_topup(self, user_id: UUID, credits: int) -> None:
        amount = max(0, int(credits or 0))
        if amount <= 0:
            return
        await self._pool.execute(
            """
            UPDATE web_subscriptions
            SET topup_credits_balance = GREATEST(
                0,
                COALESCE(topup_credits_balance, 0) - $2
            )
            WHERE user_id = $1
              AND status = 'active'
            """,
            user_id,
            amount,
        )

    async def zero_web_subscription_remaining(self, user_id: UUID) -> None:
        await self._pool.execute(
            """
            UPDATE web_subscriptions
            SET monthly_credits_used = monthly_credits_granted,
                topup_credits_balance = 0
            WHERE user_id = $1
              AND status = 'active'
            """,
            user_id,
        )
