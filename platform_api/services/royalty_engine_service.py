"""Monthly royalty allocation and ledger writing."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timezone, timedelta
from typing import Any

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.services.royalty_policy_service import RoyaltyPolicyService

logger = logging.getLogger(__name__)

MICROS_PER_USD = 1_000_000
RESERVE_HOLD_DAYS = 90


def allocate_royalties(
    rows: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Pure allocation math: eligibility, weights, caps, and rates."""
    pool_usd = float((policy.get("pool") or {}).get("amount_usd") or 0)
    pool_micros = int(round(pool_usd * MICROS_PER_USD))
    reserve_pct = float(policy.get("reserve_pct") or 0)
    reserve_micros = int(round(pool_micros * reserve_pct / 100))
    available_pool = max(0, pool_micros - reserve_micros)

    threshold_streams = int(
        policy.get("eligibility_streams")
        or (policy.get("eligibility") or {}).get("min_valid_streams")
        or 500
    )
    threshold_listeners = int(
        policy.get("eligibility_unique_listeners")
        or (policy.get("eligibility") or {}).get("min_unique_listeners")
        or 50
    )
    weights = policy.get("weights") or {}
    track_cap = int((policy.get("caps") or {}).get("per_track_weighted_streams") or 500_000)
    creator_cap_pct = float((policy.get("caps") or {}).get("per_creator_pool_pct") or 40)

    tracks: list[dict[str, Any]] = []
    creator_weighted: dict[str, int] = {}
    for row in rows:
        valid = int(row.get("valid_streams") or 0)
        unique = int(row.get("unique_listeners") or 0)
        if valid < threshold_streams or unique < threshold_listeners:
            continue
        origin = str(row.get("origin") or "ai_generated")
        weight = float(weights.get(origin, 0.3))
        weighted = min(int(round(valid * weight)), track_cap)
        creator_id = str(row["creator_id"])
        tracks.append(
            {
                "creator_id": creator_id,
                "track_id": str(row["track_id"]),
                "origin": origin,
                "valid_streams": valid,
                "unique_listeners": unique,
                "weighted_streams": weighted,
            }
        )
        creator_weighted[creator_id] = creator_weighted.get(creator_id, 0) + weighted

    total_weighted = sum(creator_weighted.values())
    if total_weighted == 0:
        return {
            "pool_micros": pool_micros,
            "reserve_micros": reserve_micros,
            "available_pool_micros": available_pool,
            "total_weighted_streams": 0,
            "rate_micros": 0,
            "allocations": [],
            "creator_totals": {},
        }

    cap_micros = int(round(pool_micros * creator_cap_pct / 100))
    remaining = available_pool
    uncapped = set(creator_weighted)
    assigned: dict[str, int] = {}

    for _ in range(6):
        total_uncapped = sum(creator_weighted[c] for c in uncapped)
        if total_uncapped <= 0:
            break
        rate = remaining / total_uncapped
        over = [c for c in uncapped if creator_weighted[c] * rate > cap_micros]
        if not over:
            break
        for creator_id in over:
            assigned[creator_id] = cap_micros
            remaining = max(0, remaining - cap_micros)
            uncapped.discard(creator_id)
        if not uncapped:
            break

    total_uncapped = sum(creator_weighted[c] for c in uncapped)
    final_rate = remaining / total_uncapped if total_uncapped > 0 else 0.0
    for creator_id in uncapped:
        assigned[creator_id] = int(round(creator_weighted[creator_id] * final_rate))

    allocations: list[dict[str, Any]] = []
    creator_totals: dict[str, int] = {}
    for track in tracks:
        creator_id = track["creator_id"]
        creator_total_weight = creator_weighted[creator_id]
        creator_amount = assigned.get(creator_id, 0)
        creator_rate = creator_amount / creator_total_weight if creator_total_weight else 0.0
        amount = int(round(track["weighted_streams"] * creator_rate))
        allocations.append({**track, "amount_micros": amount})
        creator_totals[creator_id] = creator_totals.get(creator_id, 0) + amount

    total_allocated = sum(creator_totals.values())
    if total_allocated > available_pool and creator_totals:
        largest = max(creator_totals, key=creator_totals.get)
        creator_totals[largest] -= total_allocated - available_pool

    return {
        "pool_micros": pool_micros,
        "reserve_micros": reserve_micros,
        "available_pool_micros": available_pool,
        "total_weighted_streams": total_weighted,
        "rate_micros": (available_pool / total_weighted) if total_weighted else 0,
        "allocations": allocations,
        "creator_totals": creator_totals,
    }


class RoyaltyEngineService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def calculate(
        self,
        *,
        period_start: date,
        period_end: date,
        pool_usd: float | None = None,
    ) -> dict[str, Any]:
        if period_end <= period_start:
            raise ValidationError(
                "period_end must be after period_start.",
                details={"fields": {"period_end": "invalid"}},
            )
        policy = await RoyaltyPolicyService(self._pool).get_active()
        document = dict(policy["document"])
        if pool_usd is not None:
            document["pool"] = {**(document.get("pool") or {}), "amount_usd": pool_usd}

        existing = await self._pool.fetchrow(
            """
            SELECT id, status FROM royalty_periods
            WHERE period_start = $1 AND period_end = $2
            """,
            period_start,
            period_end,
        )
        if existing and existing["status"] in {"locked", "paid"}:
            raise ValidationError(
                "This period is locked. Create an adjustment instead.",
                details={"fields": {"period": "locked"}},
            )

        rows = await self._pool.fetch(
            """
            SELECT t.user_id AS creator_id,
                   t.id AS track_id,
                   t.origin,
                   COUNT(v.id) FILTER (
                       WHERE v.status IN ('valid','royalty')
                   )::int AS valid_streams,
                   COUNT(DISTINCT v.listener_user_id) FILTER (
                       WHERE v.status IN ('valid','royalty')
                   )::int AS unique_listeners
            FROM valid_streams v
            JOIN stream_tracks t
              ON t.id = v.subject_id AND v.subject_type = 'stream_track'
            WHERE v.played_at >= $1 AND v.played_at < $2
            GROUP BY t.user_id, t.id, t.origin
            """,
            period_start,
            period_end,
        )
        allocation = allocate_royalties([dict(row) for row in rows], document)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if existing:
                    period_id = existing["id"]
                    await conn.execute(
                        """
                        UPDATE royalty_periods
                        SET policy_id = $2, pool_micros = $3, total_weighted_streams = $4,
                            rate_micros = $5, status = 'calculated', calculated_at = NOW()
                        WHERE id = $1
                        """,
                        period_id,
                        policy.get("id"),
                        allocation["pool_micros"],
                        allocation["total_weighted_streams"],
                        allocation["rate_micros"],
                    )
                else:
                    period_id = await conn.fetchval(
                        """
                        INSERT INTO royalty_periods (
                            period_start, period_end, policy_id, pool_micros,
                            total_weighted_streams, rate_micros, status, calculated_at
                        ) VALUES ($1,$2,$3,$4,$5,$6,'calculated',NOW())
                        RETURNING id
                        """,
                        period_start,
                        period_end,
                        policy.get("id"),
                        allocation["pool_micros"],
                        allocation["total_weighted_streams"],
                        allocation["rate_micros"],
                    )

                await conn.execute(
                    "DELETE FROM royalty_ledger WHERE period_id = $1",
                    period_id,
                )
                await conn.execute(
                    """
                    DELETE FROM creator_earnings
                    WHERE source = 'royalty' AND period = $1
                    """,
                    period_start,
                )

                if allocation["reserve_micros"]:
                    await conn.execute(
                        """
                        INSERT INTO royalty_ledger (
                            period_id, policy_id, entry_type, amount_micros, reason
                        ) VALUES ($1,$2,'reserve',$3,'Reserve held for disputes')
                        """,
                        period_id,
                        policy.get("id"),
                        allocation["reserve_micros"],
                    )

                for entry in allocation["allocations"]:
                    await conn.execute(
                        """
                        INSERT INTO royalty_ledger (
                            period_id, policy_id, creator_id, track_id,
                            subject_type, subject_id, entry_type,
                            weighted_streams, rate_micros, amount_micros
                        ) VALUES ($1,$2,$3,$4,'stream_track',$4,'accrual',$5,$6,$7)
                        """,
                        period_id,
                        policy.get("id"),
                        entry["creator_id"],
                        entry["track_id"],
                        entry["weighted_streams"],
                        allocation["rate_micros"],
                        entry["amount_micros"],
                    )

                label = period_start.strftime("%B %Y")
                holdback_days = int(document.get("holdback_days") or 30)
                available_at = (
                    datetime.combine(period_end, datetime.min.time(), tzinfo=timezone.utc)
                    + timedelta(days=holdback_days)
                )
                for creator_id, amount in allocation["creator_totals"].items():
                    if amount <= 0:
                        continue
                    await conn.execute(
                        """
                        INSERT INTO creator_earnings (
                            creator_id, source, source_id, period,
                            gross_micros, fee_micros, net_micros,
                            currency, status, available_at, description
                        ) VALUES ($1,'royalty',$2,$3,$4,0,$4,'USD','pending',$5,$6)
                        """,
                        creator_id,
                        str(period_id),
                        period_start,
                        amount,
                        available_at,
                        f"Royalty for {label}",
                    )

        return {
            "period_id": str(period_id),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "pool_micros": allocation["pool_micros"],
            "reserve_micros": allocation["reserve_micros"],
            "total_weighted_streams": allocation["total_weighted_streams"],
            "creators": len(allocation["creator_totals"]),
            "tracks": len(allocation["allocations"]),
            "allocated_micros": sum(allocation["creator_totals"].values()),
        }

    async def list_periods(self, limit: int = 24) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM royalty_periods
            ORDER BY period_start DESC
            LIMIT $1
            """,
            max(1, min(limit, 100)),
        )
        return {"items": [dict(row) for row in rows]}

    async def release_due_reserves(self) -> int:
        """Release every reserve whose dispute window has closed. Safe to re-run."""
        rows = await self._pool.fetch(
            """
            SELECT p.id
            FROM royalty_periods p
            WHERE p.period_end <= (CURRENT_DATE - ($1 || ' days')::interval)
              AND EXISTS (
                  SELECT 1 FROM royalty_ledger l
                  WHERE l.period_id = p.id AND l.entry_type = 'reserve'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM royalty_ledger l
                  WHERE l.period_id = p.id AND l.entry_type = 'reserve_release'
              )
            """,
            str(RESERVE_HOLD_DAYS),
        )
        released = 0
        for row in rows:
            try:
                await self.release_reserve(str(row["id"]))
                released += 1
            except (DuplicateError, NotFoundError, ValidationError):
                continue
        return released

    async def release_reserve(self, period_id: str) -> dict[str, Any]:
        """Return a period's held reserve to its creators once the dispute window closes."""
        period = await self._pool.fetchrow(
            "SELECT * FROM royalty_periods WHERE id = $1", period_id
        )
        if period is None:
            raise NotFoundError("Royalty period not found.")

        hold_until = datetime.combine(
            period["period_end"], datetime.min.time(), tzinfo=timezone.utc
        ) + timedelta(days=RESERVE_HOLD_DAYS)
        if hold_until > datetime.now(timezone.utc):
            raise ValidationError(
                "The reserve is still inside its dispute window.",
                details={
                    "fields": {"period": "not yet releasable"},
                    "hold_until": hold_until.isoformat(),
                },
            )

        reserve = await self._pool.fetchval(
            "SELECT amount_micros FROM royalty_ledger "
            "WHERE period_id = $1 AND entry_type = 'reserve'",
            period_id,
        )
        if not reserve:
            raise ValidationError(
                "This period holds no reserve.",
                details={"fields": {"period": "no reserve"}},
            )
        released_before = await self._pool.fetchval(
            "SELECT 1 FROM royalty_ledger "
            "WHERE period_id = $1 AND entry_type = 'reserve_release' LIMIT 1",
            period_id,
        )
        if released_before:
            raise DuplicateError("The reserve for this period is already released.")

        accruals = await self._pool.fetch(
            """
            SELECT creator_id, SUM(amount_micros)::bigint AS amount_micros
            FROM royalty_ledger
            WHERE period_id = $1 AND entry_type = 'accrual' AND creator_id IS NOT NULL
            GROUP BY creator_id
            """,
            period_id,
        )
        total_accrued = sum(int(row["amount_micros"] or 0) for row in accruals)
        if total_accrued <= 0:
            raise ValidationError(
                "There are no creator accruals to release against.",
                details={"fields": {"period": "no accruals"}},
            )

        reserve_micros = int(reserve)
        shares: dict[Any, int] = {}
        distributed = 0
        largest = None
        largest_amount = -1
        for row in accruals:
            share = reserve_micros * int(row["amount_micros"] or 0) // total_accrued
            shares[row["creator_id"]] = share
            distributed += share
            if int(row["amount_micros"] or 0) > largest_amount:
                largest_amount = int(row["amount_micros"] or 0)
                largest = row["creator_id"]
        # Hand the rounding remainder to the largest accrual so the reserve nets to zero.
        if largest is not None:
            shares[largest] += reserve_micros - distributed

        label = period["period_start"].strftime("%B %Y")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for creator_id, share in shares.items():
                    if share <= 0:
                        continue
                    await conn.execute(
                        """
                        INSERT INTO royalty_ledger (
                            period_id, policy_id, creator_id, entry_type,
                            amount_micros, reason
                        ) VALUES ($1,$2,$3,'reserve_release',$4,$5)
                        """,
                        period_id,
                        period["policy_id"],
                        creator_id,
                        share,
                        f"Reserve release for {label}",
                    )
                    await conn.execute(
                        """
                        INSERT INTO creator_earnings (
                            creator_id, source, source_id, period,
                            gross_micros, fee_micros, net_micros,
                            currency, status, available_at, description
                        ) VALUES ($1,'royalty',$2,$3,$4,0,$4,'USD','available',NOW(),$5)
                        """,
                        creator_id,
                        str(period_id),
                        period["period_start"],
                        share,
                        f"Reserve release for {label}",
                    )

        return {
            "period_id": str(period_id),
            "reserve_micros": reserve_micros,
            "released_micros": sum(shares.values()),
            "creators": len([value for value in shares.values() if value > 0]),
        }

    async def lock_period(self, period_id: str) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            "SELECT * FROM royalty_periods WHERE id = $1", period_id
        )
        if row is None:
            raise NotFoundError("Royalty period not found.")
        if row["status"] not in {"calculated", "open"}:
            raise ValidationError(
                "Only calculated periods can be locked.",
                details={"fields": {"period": "invalid status"}},
            )
        locked = await self._pool.fetchrow(
            """
            UPDATE royalty_periods
            SET status = 'locked', locked_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            period_id,
        )
        return {"period": dict(locked)}

async def run_reserve_release_loop(
    pool: Any,
    *,
    interval_seconds: int = 86_400,
    startup_delay: float = 120.0,
) -> None:
    """Release held reserves daily once their dispute window has closed."""
    if startup_delay:
        await asyncio.sleep(startup_delay)
    while True:
        try:
            released = await RoyaltyEngineService(pool).release_due_reserves()
            if released:
                logger.info("Released reserves for %s royalty periods.", released)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reserve release failed; retrying next interval.")
        await asyncio.sleep(max(3600, interval_seconds))

