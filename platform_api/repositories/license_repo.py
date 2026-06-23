"""License and Plan repositories with asyncpg-based CRUD operations.

Provides license key generation, assignment, revocation, status queries,
active license lookup, plan management, and plan usage tracking.

Requirements: 4.1, 4.3, 4.4
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import License, Plan
from platform_api.models.enums import LicenseStatus

logger = logging.getLogger(__name__)


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single row."""
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return all rows."""
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single value."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        ...


# ---------------------------------------------------------------------------
# Row-to-domain converters
# ---------------------------------------------------------------------------


def _row_to_license(row: Any) -> License:
    """Convert an asyncpg Record to a License domain object."""
    return License(
        id=row["id"],
        license_key=row["license_key"],
        plan_id=row["plan_id"],
        user_id=row.get("user_id"),
        status=LicenseStatus(row["status"]),
        activated_at=row.get("activated_at"),
        expires_at=row.get("expires_at"),
        revoked_at=row.get("revoked_at"),
        created_at=row["created_at"],
    )


def _row_to_plan(row: Any) -> Plan:
    """Convert an asyncpg Record to a Plan domain object."""
    return Plan(
        id=row["id"],
        name=row["name"],
        price_cents=row["price_cents"],
        billing_cycle_days=row.get("billing_cycle_days"),
        profile_allowance=row["profile_allowance"],
        monthly_song_limit=row.get("monthly_song_limit"),
        monthly_image_limit=row.get("monthly_image_limit"),
        daily_song_limit_per_channel=row["daily_song_limit_per_channel"],
        daily_image_limit_per_channel=row.get("daily_image_limit_per_channel", 7),
        is_active=row["is_active"],
        effective_from=row["effective_from"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _generate_license_key() -> str:
    """Generate a cryptographically secure 64-character hex license key."""
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# LicenseRepository
# ---------------------------------------------------------------------------


class LicenseRepository:
    """Repository for license CRUD operations using asyncpg.

    Handles license key generation, assignment to users, revocation,
    and active license queries.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def create(self, plan_id: UUID) -> License:
        """Create a new unassigned license with a generated key.

        Args:
            plan_id: The UUID of the plan this license is for.

        Returns:
            The newly created License domain object.
        """
        license_key = _generate_license_key()
        row = await self._pool.fetchrow(
            """
            INSERT INTO licenses (license_key, plan_id, status, created_at)
            VALUES ($1, $2, 'unassigned', NOW())
            RETURNING id, license_key, plan_id, user_id, status,
                      activated_at, expires_at, revoked_at, created_at
            """,
            license_key,
            plan_id,
        )
        return _row_to_license(row)

    async def get_by_id(self, license_id: UUID) -> License | None:
        """Return the license with the given ID, or None if not found.

        Args:
            license_id: The UUID of the license to look up.

        Returns:
            The License domain object, or None if no matching license exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, license_key, plan_id, user_id, status,
                   activated_at, expires_at, revoked_at, created_at
            FROM licenses
            WHERE id = $1
            """,
            license_id,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def get_by_key(self, license_key: str) -> License | None:
        """Return the license with the given key, or None if not found.

        Args:
            license_key: The 64-character hex license key to look up.

        Returns:
            The License domain object, or None if no matching license exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, license_key, plan_id, user_id, status,
                   activated_at, expires_at, revoked_at, created_at
            FROM licenses
            WHERE license_key = $1
            """,
            license_key,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def assign_to_user(
        self, license_id: UUID, user_id: UUID, plan: Plan
    ) -> License:
        """Assign a license to a user, activating it with expiration based on plan.

        Sets the license status to 'active', records the activation timestamp,
        and computes expires_at from the plan's billing_cycle_days (None for lifetime).

        Args:
            license_id: The UUID of the license to assign.
            user_id: The UUID of the user receiving the license.
            plan: The Plan domain object for computing expiration.

        Returns:
            The updated License domain object.
        """
        now = datetime.now(timezone.utc)
        expires_at: datetime | None = None
        if plan.billing_cycle_days is not None:
            expires_at = now + timedelta(days=plan.billing_cycle_days)

        row = await self._pool.fetchrow(
            """
            UPDATE licenses
            SET user_id = $2,
                status = 'active',
                activated_at = $3,
                expires_at = $4
            WHERE id = $1
            RETURNING id, license_key, plan_id, user_id, status,
                      activated_at, expires_at, revoked_at, created_at
            """,
            license_id,
            user_id,
            now,
            expires_at,
        )
        return _row_to_license(row)

    async def revoke(self, license_id: UUID) -> bool:
        """Revoke a license by setting status to 'revoked' and revoked_at to now.

        Args:
            license_id: The UUID of the license to revoke.

        Returns:
            True if the license was found and revoked, False otherwise.
        """
        result = await self._pool.execute(
            """
            UPDATE licenses
            SET status = 'revoked',
                revoked_at = NOW()
            WHERE id = $1 AND status != 'revoked'
            """,
            license_id,
        )
        return result == "UPDATE 1"

    async def get_active_for_user(self, user_id: UUID) -> License | None:
        """Find the active non-expired license for a user.

        A license is considered active if its status is 'active' and either
        it has no expiration (lifetime) or its expires_at is in the future.

        Args:
            user_id: The UUID of the user.

        Returns:
            The active License, or None if no valid license exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, license_key, plan_id, user_id, status,
                   activated_at, expires_at, revoked_at, created_at
            FROM licenses
            WHERE user_id = $1
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY activated_at DESC
            LIMIT 1
            """,
            user_id,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def has_active_license(self, user_id: str) -> bool:
        """Check if a user has an active non-expired license.

        Used by auth middleware for license validation checks.

        Args:
            user_id: The string UUID of the user.

        Returns:
            True if the user has at least one active non-expired license.
        """
        result = await self._pool.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM licenses
                WHERE user_id = $1
                  AND status = 'active'
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
            """,
            UUID(user_id),
        )
        return result is True

    async def has_duplicate_plan(self, user_id: UUID, plan_id: UUID) -> bool:
        """Check if a user already has an active license for the same plan.

        Prevents duplicate plan assignment.

        Args:
            user_id: The UUID of the user.
            plan_id: The UUID of the plan to check.

        Returns:
            True if the user already has an active license for this plan.
        """
        result = await self._pool.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM licenses
                WHERE user_id = $1
                  AND plan_id = $2
                  AND status = 'active'
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
            """,
            user_id,
            plan_id,
        )
        return result is True

    async def get_user_licenses(self, user_id: UUID) -> list[License]:
        """Return all licenses for a user, ordered by creation date descending.

        Args:
            user_id: The UUID of the user.

        Returns:
            List of License domain objects.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, license_key, plan_id, user_id, status,
                   activated_at, expires_at, revoked_at, created_at
            FROM licenses
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [_row_to_license(row) for row in rows]

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        """Revoke all active licenses for a user.

        Args:
            user_id: The UUID of the user.

        Returns:
            The number of licenses that were revoked.
        """
        result = await self._pool.execute(
            """
            UPDATE licenses
            SET status = 'revoked',
                revoked_at = NOW()
            WHERE user_id = $1 AND status = 'active'
            """,
            user_id,
        )
        # asyncpg returns "UPDATE N" where N is the affected row count
        if result.startswith("UPDATE "):
            return int(result.split(" ")[1])
        return 0


    async def get_all_paginated(
        self,
        page: int = 1,
        page_size: int = 25,
        status: str | None = None,
    ) -> tuple[list["License"], int]:
        """Return a paginated list of all licenses with optional status filter."""
        offset = (page - 1) * page_size

        if status:
            count = await self._pool.fetchval(
                "SELECT COUNT(*) FROM licenses WHERE status = $1", status
            )
            rows = await self._pool.fetch(
                """
                SELECT id, license_key, plan_id, user_id, status,
                       activated_at, expires_at, revoked_at, created_at
                FROM licenses WHERE status = $1
                ORDER BY created_at DESC LIMIT $2 OFFSET $3
                """,
                status, page_size, offset,
            )
        else:
            count = await self._pool.fetchval("SELECT COUNT(*) FROM licenses")
            rows = await self._pool.fetch(
                """
                SELECT id, license_key, plan_id, user_id, status,
                       activated_at, expires_at, revoked_at, created_at
                FROM licenses ORDER BY created_at DESC LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )

        return [_row_to_license(row) for row in rows], count or 0


# ---------------------------------------------------------------------------
# PlanRepository
# ---------------------------------------------------------------------------


class PlanRepository:
    """Repository for plan CRUD operations and default seeding.

    Manages subscription plan configurations (Monthly, Yearly, Lifetime)
    and provides plan usage tracking for quota consumption.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def get_all(self) -> list[Plan]:
        """Return all plans ordered by price ascending.

        Returns:
            List of Plan domain objects.
        """
        rows = await self._pool.fetch(
            """
            SELECT id, name, price_cents, billing_cycle_days, profile_allowance,
                   monthly_song_limit, monthly_image_limit,
                   daily_song_limit_per_channel, daily_image_limit_per_channel,
                   is_active, effective_from, created_at, updated_at
            FROM plans
            ORDER BY price_cents ASC
            """
        )
        return [_row_to_plan(row) for row in rows]

    async def create(
        self,
        name: str,
        price_cents: int,
        profile_allowance: int,
        monthly_song_limit: int | None = None,
        monthly_image_limit: int | None = None,
        billing_cycle_days: int | None = None,
        daily_song_limit_per_channel: int = 7,
        daily_image_limit_per_channel: int = 7,
    ) -> Plan:
        """Create a new plan.

        Args:
            name: Unique plan name.
            price_cents: Price in cents.
            profile_allowance: Max channel profiles allowed.
            monthly_song_limit: Monthly song limit (None for unlimited).
            monthly_image_limit: Monthly image limit (None for unlimited).
            billing_cycle_days: Billing cycle in days (None for lifetime).
            daily_song_limit_per_channel: Daily song limit per channel.
            daily_image_limit_per_channel: Daily image limit per channel.

        Returns:
            The newly created Plan domain object.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO plans (name, price_cents, billing_cycle_days, profile_allowance,
                               monthly_song_limit, monthly_image_limit,
                               daily_song_limit_per_channel, daily_image_limit_per_channel,
                               is_active, effective_from, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true, NOW(), NOW(), NOW())
            RETURNING id, name, price_cents, billing_cycle_days, profile_allowance,
                      monthly_song_limit, monthly_image_limit,
                      daily_song_limit_per_channel, daily_image_limit_per_channel,
                      is_active, effective_from, created_at, updated_at
            """,
            name,
            price_cents,
            billing_cycle_days,
            profile_allowance,
            monthly_song_limit,
            monthly_image_limit,
            daily_song_limit_per_channel,
            daily_image_limit_per_channel,
        )
        return _row_to_plan(row)

    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        """Return the plan with the given ID, or None if not found.

        Args:
            plan_id: The UUID of the plan to look up.

        Returns:
            The Plan domain object, or None if no matching plan exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, name, price_cents, billing_cycle_days, profile_allowance,
                   monthly_song_limit, monthly_image_limit,
                   daily_song_limit_per_channel, daily_image_limit_per_channel,
                   is_active, effective_from, created_at, updated_at
            FROM plans
            WHERE id = $1
            """,
            plan_id,
        )
        if row is None:
            return None
        return _row_to_plan(row)

    async def get_by_name(self, name: str) -> Plan | None:
        """Return the plan with the given name, or None if not found.

        Args:
            name: The plan name to look up (e.g. 'monthly', 'yearly', 'lifetime').

        Returns:
            The Plan domain object, or None if no matching plan exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, name, price_cents, billing_cycle_days, profile_allowance,
                   monthly_song_limit, monthly_image_limit,
                   daily_song_limit_per_channel, daily_image_limit_per_channel,
                   is_active, effective_from, created_at, updated_at
            FROM plans
            WHERE name = $1
            """,
            name,
        )
        if row is None:
            return None
        return _row_to_plan(row)

    async def update(self, plan_id: UUID, **fields: Any) -> Plan | None:
        """Update specified fields on a plan record.

        Only the provided keyword arguments are updated. The ``updated_at``
        timestamp is always refreshed.

        Args:
            plan_id: The UUID of the plan to update.
            **fields: Column names and their new values.

        Returns:
            The updated Plan domain object, or None if not found.
        """
        if not fields:
            return await self.get_by_id(plan_id)

        set_parts: list[str] = []
        values: list[Any] = []
        param_idx = 1

        for col, val in fields.items():
            set_parts.append(f"{col} = ${param_idx}")
            values.append(val)
            param_idx += 1

        set_parts.append(f"updated_at = ${param_idx}")
        values.append(datetime.now(timezone.utc))
        param_idx += 1

        values.append(plan_id)

        query = f"""
            UPDATE plans
            SET {', '.join(set_parts)}
            WHERE id = ${param_idx}
            RETURNING id, name, price_cents, billing_cycle_days, profile_allowance,
                      monthly_song_limit, monthly_image_limit,
                      daily_song_limit_per_channel, daily_image_limit_per_channel,
                      is_active, effective_from, created_at, updated_at
        """

        row = await self._pool.fetchrow(query, *values)
        if row is None:
            return None
        return _row_to_plan(row)

    async def seed_defaults(self) -> None:
        """Insert default plans if they don't already exist.

        Creates the three standard plans:
        - Monthly: $79/30-day cycle, 2 profiles, 420 monthly songs
        - Yearly: $699/365-day cycle, 4 profiles, 840 monthly songs
        - Lifetime: $1499 one-time, 5 profiles, unlimited songs
        """
        defaults = [
            {
                "name": "monthly",
                "price_cents": 7900,
                "billing_cycle_days": 30,
                "profile_allowance": 2,
                "monthly_song_limit": 420,
                "daily_song_limit_per_channel": 7,
            },
            {
                "name": "yearly",
                "price_cents": 69900,
                "billing_cycle_days": 365,
                "profile_allowance": 4,
                "monthly_song_limit": 840,
                "daily_song_limit_per_channel": 7,
            },
            {
                "name": "lifetime",
                "price_cents": 149900,
                "billing_cycle_days": None,
                "profile_allowance": 5,
                "monthly_song_limit": None,
                "daily_song_limit_per_channel": 7,
            },
        ]

        for plan_data in defaults:
            await self._pool.execute(
                """
                INSERT INTO plans (name, price_cents, billing_cycle_days,
                                   profile_allowance, monthly_song_limit,
                                   daily_song_limit_per_channel, is_active,
                                   effective_from, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, true, NOW(), NOW(), NOW())
                ON CONFLICT (name) DO NOTHING
                """,
                plan_data["name"],
                plan_data["price_cents"],
                plan_data["billing_cycle_days"],
                plan_data["profile_allowance"],
                plan_data["monthly_song_limit"],
                plan_data["daily_song_limit_per_channel"],
            )

        logger.info("Default plans seeded (skipped existing).")

    async def get_user_active_plan(self, user_id: UUID) -> Plan | None:
        """Get the plan associated with the user's active license.

        Joins plans → licenses to find the plan for the user's currently
        active (non-expired) license. A license is considered active when
        its status is 'active' and it has not expired.

        Args:
            user_id: The UUID of the user.

        Returns:
            The Plan domain object, or None if no active plan exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT p.id, p.name, p.price_cents, p.billing_cycle_days,
                   p.profile_allowance, p.monthly_song_limit, p.monthly_image_limit,
                   p.daily_song_limit_per_channel, p.daily_image_limit_per_channel,
                   p.is_active, p.effective_from, p.created_at, p.updated_at
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
        if row is None:
            return None
        return _row_to_plan(row)

    # -----------------------------------------------------------------------
    # Plan Usage Tracking
    # -----------------------------------------------------------------------

    async def get_or_create_usage(
        self,
        user_id: UUID,
        license_id: UUID,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        """Get or create a plan usage record for the given period.

        If no record exists for the user/license/period combination, one is
        created with songs_used=0.

        Args:
            user_id: The UUID of the user.
            license_id: The UUID of the license.
            period_start: The start date of the billing period.
            period_end: The end date of the billing period.

        Returns:
            A dict with keys: id, user_id, license_id, period_start,
            period_end, songs_used.
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO plan_usage (user_id, license_id, period_start, period_end, songs_used)
            VALUES ($1, $2, $3, $4, 0)
            ON CONFLICT (user_id, license_id, period_start)
            DO UPDATE SET period_end = EXCLUDED.period_end
            RETURNING id, user_id, license_id, period_start, period_end, songs_used
            """,
            user_id,
            license_id,
            period_start,
            period_end,
        )
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "license_id": row["license_id"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "songs_used": row["songs_used"],
        }

    async def increment_usage(
        self, user_id: UUID, license_id: UUID, period_start: date
    ) -> int:
        """Increment the songs_used count for the current period.

        Args:
            user_id: The UUID of the user.
            license_id: The UUID of the license.
            period_start: The start date of the current billing period.

        Returns:
            The new songs_used count after incrementing.
        """
        result = await self._pool.fetchval(
            """
            UPDATE plan_usage
            SET songs_used = songs_used + 1
            WHERE user_id = $1
              AND license_id = $2
              AND period_start = $3
            RETURNING songs_used
            """,
            user_id,
            license_id,
            period_start,
        )
        return result if result is not None else 0

    async def get_current_usage(self, user_id: UUID, license_id: UUID) -> int:
        """Get the songs_used count for the current billing period.

        Looks up the usage record where today falls between period_start
        and period_end.

        Args:
            user_id: The UUID of the user.
            license_id: The UUID of the license.

        Returns:
            The current songs_used count, or 0 if no active period found.
        """
        result = await self._pool.fetchval(
            """
            SELECT songs_used
            FROM plan_usage
            WHERE user_id = $1
              AND license_id = $2
              AND period_start <= CURRENT_DATE
              AND period_end >= CURRENT_DATE
            ORDER BY period_start DESC
            LIMIT 1
            """,
            user_id,
            license_id,
        )
        return result if result is not None else 0
