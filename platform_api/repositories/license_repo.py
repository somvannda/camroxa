"""License and Plan repositories with asyncpg-based CRUD operations.

Provides license key generation, assignment, revocation, status queries,
active license lookup, plan management, and plan usage tracking.

Requirements: 4.1, 4.3, 4.4
"""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import License, Plan
from platform_api.models.enums import LicenseStatus

_LICENSE_SELECT = """
    id, license_key, plan_id, user_id, status,
    activated_at, expires_at, revoked_at,
    profile_addon_slots, profile_addon_pending,
    pending_plan_id, pending_plan_effective_at,
    created_at
"""

_PLAN_SELECT = """
    id, name, price_cents, billing_cycle_days, profile_allowance,
    monthly_song_limit, monthly_image_limit, monthly_draft_limit,
    monthly_video_limit, monthly_merge_limit,
    daily_song_limit_per_channel, daily_image_limit_per_channel,
    daily_draft_limit_per_channel,
    daily_video_limit, daily_merge_limit,
    included_wallet_credits, plan_kind,
    plan_type, monthly_credits, daily_credits, features, pricing_features, pricing_credit_lines, is_public, display_order,
    is_active, effective_from, created_at, updated_at
"""


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
        profile_addon_slots=int(row.get("profile_addon_slots") or 0),
        profile_addon_pending=int(row.get("profile_addon_pending") or 0),
        pending_plan_id=row.get("pending_plan_id"),
        pending_plan_effective_at=row.get("pending_plan_effective_at"),
        created_at=row["created_at"],
    )


def _parse_plan_features(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_pricing_features(value: Any) -> list[str]:
    from platform_api.services.pricing_display import normalize_pricing_features

    return normalize_pricing_features(value)


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
        monthly_draft_limit=row.get("monthly_draft_limit"),
        monthly_video_limit=row.get("monthly_video_limit"),
        monthly_merge_limit=row.get("monthly_merge_limit"),
        daily_song_limit_per_channel=row["daily_song_limit_per_channel"],
        daily_image_limit_per_channel=row.get("daily_image_limit_per_channel", 2),
        daily_draft_limit_per_channel=int(row.get("daily_draft_limit_per_channel") or 300),
        daily_video_limit=int(row.get("daily_video_limit") or 10),
        daily_merge_limit=int(row.get("daily_merge_limit") or 1),
        included_wallet_credits=int(row.get("included_wallet_credits") or 0),
        plan_kind=str(row.get("plan_kind") or "subscription"),
        plan_type=str(row.get("plan_type") or "desktop_pro"),
        monthly_credits=row.get("monthly_credits"),
        daily_credits=int(row.get("daily_credits") or 0),
        features=_parse_plan_features(row.get("features")),
        pricing_features=_parse_pricing_features(row.get("pricing_features")),
        pricing_credit_lines=_parse_pricing_features(row.get("pricing_credit_lines")),
        is_public=bool(row.get("is_public") or False),
        display_order=int(row.get("display_order") or 0),
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
                      activated_at, expires_at, revoked_at,
                      profile_addon_slots, profile_addon_pending, created_at
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
            f"""
            SELECT {_LICENSE_SELECT}
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
            f"""
            SELECT {_LICENSE_SELECT}
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
                      activated_at, expires_at, revoked_at,
                      profile_addon_slots, profile_addon_pending, created_at
            """,
            license_id,
            user_id,
            now,
            expires_at,
        )
        return _row_to_license(row)

    async def change_plan(
        self, license_id: UUID, plan_id: UUID, plan: Plan
    ) -> License | None:
        """Switch an existing license to a new plan without revoking add-on fields."""
        now = datetime.now(timezone.utc)
        expires_at: datetime | None = None
        if plan.billing_cycle_days is not None:
            expires_at = now + timedelta(days=plan.billing_cycle_days)

        row = await self._pool.fetchrow(
            """
            UPDATE licenses
            SET plan_id = $2,
                status = 'active',
                activated_at = $3,
                expires_at = $4,
                revoked_at = NULL
            WHERE id = $1
            RETURNING id, license_key, plan_id, user_id, status,
                      activated_at, expires_at, revoked_at,
                      profile_addon_slots, profile_addon_pending, created_at
            """,
            license_id,
            plan_id,
            now,
            expires_at,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def extend_license(self, license_id: UUID, days: int) -> License | None:
        """Add ``days`` to an active license, counting from its current expiry.

        Used for same-plan renewals: renewing early must not drop the remaining
        days. ``GREATEST(expires_at, NOW())`` means an already-lapsed license
        restarts from now, while an active one stacks the new period on top of
        the existing expiry. ``activated_at`` is left untouched so the monthly
        credit grant still rolls at the natural period boundary.
        """
        extension_days = max(1, int(days or 30))
        row = await self._pool.fetchrow(
            """
            UPDATE licenses
            SET expires_at = GREATEST(COALESCE(expires_at, NOW()), NOW())
                              + ($2 * INTERVAL '1 day'),
                revoked_at = NULL,
                status = 'active'
            WHERE id = $1
            RETURNING id, license_key, plan_id, user_id, status,
                      activated_at, expires_at, revoked_at,
                      profile_addon_slots, profile_addon_pending, created_at
            """,
            license_id,
            extension_days,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def schedule_pending_plan(
        self,
        license_id: UUID,
        pending_plan_id: UUID,
        *,
        effective_at: datetime,
    ) -> License | None:
        row = await self._pool.fetchrow(
            f"""
            UPDATE licenses
            SET pending_plan_id = $2,
                pending_plan_effective_at = $3
            WHERE id = $1
            RETURNING {_LICENSE_SELECT.strip()}
            """,
            license_id,
            pending_plan_id,
            effective_at,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def clear_pending_plan(self, license_id: UUID) -> License | None:
        row = await self._pool.fetchrow(
            f"""
            UPDATE licenses
            SET pending_plan_id = NULL,
                pending_plan_effective_at = NULL
            WHERE id = $1
            RETURNING {_LICENSE_SELECT.strip()}
            """,
            license_id,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def apply_pending_plan_if_due(self, license_id: UUID, plan_repo: Any) -> License | None:
        license_obj = await self.get_by_id(license_id)
        if license_obj is None or license_obj.pending_plan_id is None:
            return license_obj
        effective_at = license_obj.pending_plan_effective_at
        if effective_at is None:
            return license_obj
        now = datetime.now(timezone.utc)
        effective = effective_at if effective_at.tzinfo else effective_at.replace(tzinfo=timezone.utc)
        if effective > now:
            return license_obj
        pending_plan = await plan_repo.get_by_id(license_obj.pending_plan_id)
        if pending_plan is None:
            return await self.clear_pending_plan(license_id)
        updated = await self.change_plan(license_id, pending_plan.id, pending_plan)
        if updated is None:
            return None
        return await self.clear_pending_plan(license_id)

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
        stale_rows = await self._pool.fetch(
            """
            SELECT id FROM licenses
            WHERE user_id = $1
              AND status = 'active'
              AND pending_plan_id IS NOT NULL
              AND pending_plan_effective_at IS NOT NULL
              AND pending_plan_effective_at <= NOW()
            """,
            user_id,
        )
        if stale_rows:
            plan_repo = PlanRepository(self._pool)
            for stale in stale_rows:
                await self.apply_pending_plan_if_due(stale["id"], plan_repo)

        row = await self._pool.fetchrow(
            f"""
            SELECT {_LICENSE_SELECT}
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

    async def get_latest_license_for_user(self, user_id: UUID) -> License | None:
        """Return the user's most recent non-revoked license (active or expired).

        Unlike ``get_active_for_user`` this also matches a license whose
        ``expires_at`` has already passed, so a lapsed paid plan can still be
        renewed for the next period.
        """
        row = await self._pool.fetchrow(
            f"""
            SELECT {_LICENSE_SELECT}
            FROM licenses
            WHERE user_id = $1
              AND status IN ('active', 'expired')
            ORDER BY activated_at DESC NULLS LAST, created_at DESC
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

    async def has_paid_desktop_access(self, user_id: str) -> bool:
        """True when the user has an active paid license or paid web subscription.

        Free ($0) plans cannot use the desktop studio. Hidden $79 and public
        Starter / Creator / Studio all qualify while the period is unexpired.
        """
        result = await self._pool.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM licenses l
                JOIN plans p ON p.id = l.plan_id
                WHERE l.user_id = $1
                  AND l.status = 'active'
                  AND (l.expires_at IS NULL OR l.expires_at > NOW())
                  AND COALESCE(p.price_cents, 0) > 0
            )
            OR EXISTS(
                SELECT 1
                FROM web_subscriptions ws
                JOIN plans p ON p.id = ws.plan_id
                WHERE ws.user_id = $1
                  AND ws.status = 'active'
                  AND ws.current_period_end > NOW()
                  AND COALESCE(p.price_cents, 0) > 0
            )
            """,
            UUID(user_id),
        )
        return result is True

    async def requires_active_license_for_wallet(self, user_id: UUID) -> bool:
        """True when the user's latest plan is a subscription (wallet needs active license)."""
        from platform_api.models.enums import PlanType

        row = await self._pool.fetchrow(
            """
            SELECT p.name, p.price_cents, p.billing_cycle_days, p.monthly_song_limit
            FROM licenses l
            INNER JOIN plans p ON p.id = l.plan_id
            WHERE l.user_id = $1
            ORDER BY l.activated_at DESC NULLS LAST, l.created_at DESC
            LIMIT 1
            """,
            user_id,
        )
        if row is None:
            return False
        name = (row["name"] or "").strip().lower()
        if name == PlanType.LIFETIME:
            return False
        if name in (PlanType.MONTHLY, PlanType.YEARLY):
            return True
        return (
            row.get("billing_cycle_days") is not None
            and row.get("monthly_song_limit") is not None
            and int(row.get("price_cents") or 0) > 0
        )

    async def get_user_license_expires_at(self, user_id: UUID) -> datetime | None:
        """Return expires_at for the user's current active license, if any."""
        return await self._pool.fetchval(
            """
            SELECT expires_at
            FROM licenses
            WHERE user_id = $1
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY activated_at DESC NULLS LAST
            LIMIT 1
            """,
            user_id,
        )

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
            f"""
            SELECT {_LICENSE_SELECT}
            FROM licenses
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [_row_to_license(row) for row in rows]

    async def set_profile_addon_slots(self, license_id: UUID, slots: int) -> License | None:
        """Set active profile add-on slots (multiples of 2 channels)."""
        if slots < 0 or slots > 8:
            raise ValueError("profile_addon_slots must be between 0 and 8.")
        if slots % 2 != 0:
            raise ValueError("profile_addon_slots must be a multiple of 2.")

        row = await self._pool.fetchrow(
            f"""
            UPDATE licenses
            SET profile_addon_slots = $2
            WHERE id = $1
            RETURNING {_LICENSE_SELECT}
            """,
            license_id,
            slots,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def set_profile_addon_pending(self, license_id: UUID, pending: int) -> License | None:
        """Set pending profile add-on slots awaiting onboarding."""
        if pending < 0 or pending > 8:
            raise ValueError("profile_addon_pending must be between 0 and 8.")
        if pending % 2 != 0:
            raise ValueError("profile_addon_pending must be a multiple of 2.")

        row = await self._pool.fetchrow(
            f"""
            UPDATE licenses
            SET profile_addon_pending = $2
            WHERE id = $1
            RETURNING {_LICENSE_SELECT}
            """,
            license_id,
            pending,
        )
        if row is None:
            return None
        return _row_to_license(row)

    async def add_profile_addon_pending(self, license_id: UUID, add_channels: int) -> License | None:
        """Increment pending add-on slots (payment or admin grant)."""
        license_obj = await self.get_by_id(license_id)
        if license_obj is None:
            return None
        new_pending = int(license_obj.profile_addon_pending or 0) + int(add_channels)
        return await self.set_profile_addon_pending(license_id, new_pending)

    async def add_profile_addon_slots(self, license_id: UUID, add_channels: int) -> License | None:
        """Increment active profile add-on slots by the given channel count."""
        license_obj = await self.get_by_id(license_id)
        if license_obj is None:
            return None
        new_slots = int(license_obj.profile_addon_slots or 0) + int(add_channels)
        return await self.set_profile_addon_slots(license_id, new_slots)

    async def activate_profile_addon_pending(
        self, license_id: UUID, channels: int = 2
    ) -> License | None:
        """Move pending add-on slots to active after onboarding completes."""
        if channels <= 0 or channels % 2 != 0:
            raise ValueError("Activation must be in multiples of 2 channels.")

        license_obj = await self.get_by_id(license_id)
        if license_obj is None:
            return None

        pending = int(license_obj.profile_addon_pending or 0)
        if pending < channels:
            raise ValueError("Not enough pending add-on slots to activate.")

        active = int(license_obj.profile_addon_slots or 0)
        row = await self._pool.fetchrow(
            f"""
            UPDATE licenses
            SET profile_addon_slots = $2,
                profile_addon_pending = $3
            WHERE id = $1
            RETURNING {_LICENSE_SELECT}
            """,
            license_id,
            active + channels,
            pending - channels,
        )
        if row is None:
            return None
        return _row_to_license(row)

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
                f"""
                SELECT {_LICENSE_SELECT}
                FROM licenses WHERE status = $1
                ORDER BY created_at DESC LIMIT $2 OFFSET $3
                """,
                status, page_size, offset,
            )
        else:
            count = await self._pool.fetchval("SELECT COUNT(*) FROM licenses")
            rows = await self._pool.fetch(
                f"""
                SELECT {_LICENSE_SELECT}
                FROM licenses ORDER BY created_at DESC LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )

        return [_row_to_license(row) for row in rows], count or 0


# ---------------------------------------------------------------------------
# PlanRepository
# ---------------------------------------------------------------------------


class PlanRepository:
    """Repository for plan CRUD operations.

    Reads and writes subscription plan rows from the ``plans`` table.
    Plans are created and managed only via Admin Portal — this repo does
    not bootstrap or seed default tiers.

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
            f"""
            SELECT {_PLAN_SELECT}
            FROM plans
            ORDER BY plan_kind ASC, price_cents ASC
            """
        )
        return [_row_to_plan(row) for row in rows]

    async def get_subscriber_counts(self, plan_ids: list[UUID]) -> dict[UUID, int]:
        """Return assigned-license counts for the given plans.

        A plan is considered to have subscribers if it has license rows that
        are assigned to a user (`user_id IS NOT NULL`), regardless of current
        license status. This keeps historical subscriptions from being deleted
        along with the plan record.
        """
        if not plan_ids:
            return {}

        rows = await self._pool.fetch(
            """
            SELECT plan_id, COUNT(*)::int AS subscriber_count
            FROM licenses
            WHERE plan_id = ANY($1::uuid[])
              AND user_id IS NOT NULL
            GROUP BY plan_id
            """,
            plan_ids,
        )
        return {
            row["plan_id"]: int(row["subscriber_count"] or 0)
            for row in rows
        }

    async def create(
        self,
        name: str,
        price_cents: int,
        profile_allowance: int,
        monthly_song_limit: int | None = None,
        monthly_image_limit: int | None = None,
        monthly_draft_limit: int | None = None,
        monthly_video_limit: int | None = None,
        monthly_merge_limit: int | None = None,
        billing_cycle_days: int | None = None,
        daily_song_limit_per_channel: int = 7,
        daily_image_limit_per_channel: int = 7,
        daily_draft_limit_per_channel: int = 300,
        daily_video_limit: int = 10,
        daily_merge_limit: int = 1,
        plan_kind: str = "subscription",
    ) -> Plan:
        """Create a new plan."""
        row = await self._pool.fetchrow(
            """
            INSERT INTO plans (name, price_cents, billing_cycle_days, profile_allowance,
                               monthly_song_limit, monthly_image_limit, monthly_draft_limit,
                               monthly_video_limit, monthly_merge_limit,
                               daily_song_limit_per_channel, daily_image_limit_per_channel,
                               daily_draft_limit_per_channel,
                               daily_video_limit, daily_merge_limit,
                               plan_kind,
                               is_active, effective_from, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, true, NOW(), NOW(), NOW())
            RETURNING {_PLAN_SELECT}
            """,
            name,
            price_cents,
            billing_cycle_days,
            profile_allowance,
            monthly_song_limit,
            monthly_image_limit,
            monthly_draft_limit,
            monthly_video_limit,
            monthly_merge_limit,
            daily_song_limit_per_channel,
            daily_image_limit_per_channel,
            daily_draft_limit_per_channel,
            daily_video_limit,
            daily_merge_limit,
            plan_kind,
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
            f"""
            SELECT {_PLAN_SELECT}
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
            f"""
            SELECT {_PLAN_SELECT}
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
            RETURNING {_PLAN_SELECT}
        """

        row = await self._pool.fetchrow(query, *values)
        if row is None:
            return None
        return _row_to_plan(row)

    async def delete_if_no_subscribers(self, plan_id: UUID) -> bool:
        """Delete a plan only when it has never been assigned to a user.

        Before deleting the plan record, this removes dependent promotional
        offers and unassigned license inventory for that plan.

        Returns:
            True if the plan was deleted, False if it was not found.

        Raises:
            ValidationError: If the plan has one or more subscribed users.
        """
        from platform_api.exceptions import ValidationError

        subscriber_count = int(
            await self._pool.fetchval(
                """
                SELECT COUNT(*)::int
                FROM licenses
                WHERE plan_id = $1
                  AND user_id IS NOT NULL
                """,
                plan_id,
            )
            or 0
        )
        if subscriber_count > 0:
            raise ValidationError(
                message="Cannot permanently delete a plan that has subscribed users.",
                details={
                    "plan_id": str(plan_id),
                    "subscriber_count": subscriber_count,
                },
            )

        await self._pool.execute("DELETE FROM plan_offers WHERE plan_id = $1", plan_id)
        await self._pool.execute(
            "DELETE FROM licenses WHERE plan_id = $1 AND user_id IS NULL",
            plan_id,
        )
        deleted_id = await self._pool.fetchval(
            "DELETE FROM plans WHERE id = $1 RETURNING id",
            plan_id,
        )
        return deleted_id is not None

    async def get_by_plan_type(self, plan_type: str) -> list[Plan]:
        """Return plans filtered by plan_type ordered for admin display."""
        rows = await self._pool.fetch(
            f"""
            SELECT {_PLAN_SELECT}
            FROM plans
            WHERE plan_type = $1
            ORDER BY display_order ASC, billing_cycle_days ASC, name ASC
            """,
            plan_type,
        )
        return [_row_to_plan(row) for row in rows]

    async def get_web_music_subscriber_counts(self, plan_ids: list[UUID]) -> dict[UUID, int]:
        """Return active web subscription counts per plan."""
        if not plan_ids:
            return {}
        rows = await self._pool.fetch(
            """
            SELECT plan_id, COUNT(*)::int AS subscriber_count
            FROM web_subscriptions
            WHERE plan_id = ANY($1::uuid[])
              AND status IN ('active', 'past_due')
            GROUP BY plan_id
            """,
            plan_ids,
        )
        return {
            row["plan_id"]: int(row["subscriber_count"] or 0)
            for row in rows
        }

    async def create_web_music(
        self,
        *,
        name: str,
        price_cents: int,
        billing_cycle_days: int,
        monthly_credits: int,
        features: dict[str, Any],
        is_public: bool,
        display_order: int,
    ) -> Plan:
        """Create a web music subscription plan row."""
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO plans (
                name, plan_type, price_cents, billing_cycle_days,
                monthly_credits, profile_allowance,
                monthly_song_limit, daily_song_limit_per_channel,
                features, is_public, display_order,
                plan_kind, is_active, effective_from, created_at, updated_at
            )
            VALUES (
                $1, 'web_music', $2, $3,
                $4, 1,
                NULL, 999,
                $5::jsonb, $6, $7,
                'subscription', true, NOW(), NOW(), NOW()
            )
            RETURNING {_PLAN_SELECT}
            """,
            name,
            price_cents,
            billing_cycle_days,
            monthly_credits,
            json.dumps(features),
            is_public,
            display_order,
        )
        return _row_to_plan(row)

    async def delete_web_music_if_no_subscribers(self, plan_id: UUID) -> bool:
        """Delete a web music plan when it has no active web subscriptions."""
        from platform_api.exceptions import ValidationError

        existing = await self.get_by_id(plan_id)
        if existing is None:
            return False
        if str(getattr(existing, "plan_type", "desktop_pro")) != "web_music":
            raise ValidationError(
                message="Plan is not a web music plan.",
                details={"plan_id": str(plan_id)},
            )

        subscriber_count = int(
            await self._pool.fetchval(
                """
                SELECT COUNT(*)::int
                FROM web_subscriptions
                WHERE plan_id = $1
                  AND status IN ('active', 'past_due', 'cancelled')
                """,
                plan_id,
            )
            or 0
        )
        if subscriber_count > 0:
            raise ValidationError(
                message="Cannot permanently delete a web music plan that has subscribers.",
                details={
                    "plan_id": str(plan_id),
                    "subscriber_count": subscriber_count,
                },
            )

        deleted_id = await self._pool.fetchval(
            "DELETE FROM plans WHERE id = $1 AND plan_type = 'web_music' RETURNING id",
            plan_id,
        )
        return deleted_id is not None

    async def get_user_active_subscription_context(
        self, user_id: UUID
    ) -> "ActiveSubscriptionContext | None":
        """Return active license + plan context for quota period calculations."""
        from platform_api.services.billing_period_service import ActiveSubscriptionContext

        row = await self._pool.fetchrow(
            """
            SELECT p.id, p.name, p.price_cents, p.billing_cycle_days,
                   p.profile_allowance, p.monthly_song_limit, p.monthly_image_limit,
                   p.monthly_draft_limit,
                   p.monthly_video_limit, p.monthly_merge_limit,
                   p.daily_song_limit_per_channel, p.daily_image_limit_per_channel,
                   p.daily_draft_limit_per_channel,
                   p.daily_video_limit, p.daily_merge_limit,
                   p.included_wallet_credits,
                   p.is_active, p.effective_from, p.created_at, p.updated_at,
                   l.id AS license_id, l.activated_at,
                   l.profile_addon_slots, l.profile_addon_pending
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
        return ActiveSubscriptionContext(
            plan=_row_to_plan(row),
            license_id=row["license_id"],
            activated_at=row.get("activated_at"),
            profile_addon_slots=int(row.get("profile_addon_slots") or 0),
            profile_addon_pending=int(row.get("profile_addon_pending") or 0),
        )

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
                   p.monthly_draft_limit,
                   p.monthly_video_limit, p.monthly_merge_limit,
                   p.daily_song_limit_per_channel, p.daily_image_limit_per_channel,
                   p.daily_draft_limit_per_channel,
                   p.daily_video_limit, p.daily_merge_limit,
                   p.included_wallet_credits,
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

    async def sync_songs_used_for_period(
        self,
        user_id: UUID,
        license_id: UUID,
        period_start: date,
        period_end: date,
        songs_used: int,
    ) -> None:
        """Keep plan_usage aligned with authoritative usage_tracking for admin reporting."""
        await self.get_or_create_usage(
            user_id=user_id,
            license_id=license_id,
            period_start=period_start,
            period_end=period_end,
        )
        await self._pool.execute(
            """
            UPDATE plan_usage
            SET songs_used = $4
            WHERE user_id = $1
              AND license_id = $2
              AND period_start = $3
            """,
            user_id,
            license_id,
            period_start,
            max(0, int(songs_used)),
        )

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
