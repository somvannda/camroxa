"""Database access for creator applications, verification, and badges."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID


class CreatorProgramRepository:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    async def get_open_application(self, user_id: UUID | str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM creator_applications
            WHERE user_id = $1
              AND status IN ('submitted','in_review','changes_requested')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

    async def get_latest_application(self, user_id: UUID | str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT * FROM creator_applications
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )
        return dict(row) if row else None

    async def insert_application(
        self,
        *,
        user_id: UUID | str,
        payload: dict[str, Any],
        requested_tier: str = "verified",
        sla_days: int = 3,
    ) -> dict[str, Any]:
        sla_due = datetime.now(timezone.utc) + timedelta(days=sla_days)
        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_applications (
                user_id, version, requested_tier, status, payload,
                submitted_at, sla_due_at, updated_at
            ) VALUES ($1, 1, $2, 'submitted', $3::jsonb, NOW(), $4, NOW())
            RETURNING *
            """,
            user_id,
            requested_tier,
            json.dumps(payload),
            sla_due,
        )
        return dict(row)

    async def resubmit_application(
        self,
        application_id: UUID | str,
        *,
        payload: dict[str, Any],
        sla_days: int = 3,
    ) -> dict[str, Any]:
        sla_due = datetime.now(timezone.utc) + timedelta(days=sla_days)
        row = await self._pool.fetchrow(
            """
            UPDATE creator_applications
            SET payload = $2::jsonb,
                version = version + 1,
                status = 'submitted',
                submitted_at = NOW(),
                sla_due_at = $3,
                reviewed_by = NULL,
                reviewed_at = NULL,
                decision_reason = NULL,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            application_id,
            json.dumps(payload),
            sla_due,
        )
        return dict(row) if row else {}

    async def set_application_status(
        self,
        application_id: UUID | str,
        *,
        status: str,
        reviewer_id: UUID | str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            UPDATE creator_applications
            SET status = $2,
                reviewed_by = COALESCE($3, reviewed_by),
                reviewed_at = CASE WHEN $2 IN ('in_review','approved','rejected','changes_requested') THEN NOW() ELSE reviewed_at END,
                decision_reason = $4,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            application_id,
            status,
            reviewer_id,
            reason,
        )
        return dict(row) if row else {}

    async def list_applications(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT a.*, u.email, u.display_name AS user_display_name,
                   cp.handle, cp.tier AS creator_tier
            FROM creator_applications a
            JOIN users u ON u.id = a.user_id
            LEFT JOIN creator_profiles cp ON cp.user_id = a.user_id
            WHERE ($1::text IS NULL OR a.status = $1)
            ORDER BY a.submitted_at DESC NULLS LAST, a.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            status,
            max(1, min(limit, 100)),
            max(0, offset),
        )
        return [dict(row) for row in rows]

    async def count_applications(self, *, status: str | None = None) -> int:
        value = await self._pool.fetchval(
            "SELECT COUNT(*) FROM creator_applications WHERE ($1::text IS NULL OR status = $1)",
            status,
        )
        return int(value or 0)

    async def get_application(self, application_id: UUID | str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM creator_applications WHERE id = $1", application_id
        )
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    async def insert_verification(
        self,
        *,
        user_id: UUID | str,
        kind: str,
        evidence_ref: str | None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_verifications (user_id, kind, status, evidence_ref)
            VALUES ($1, $2, 'pending', $3)
            RETURNING *
            """,
            user_id,
            kind,
            evidence_ref,
        )
        return dict(row)

    async def list_verifications(self, user_id: UUID | str) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM creator_verifications
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [dict(row) for row in rows]

    async def list_pending_verifications(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT v.*, u.email, u.display_name AS user_display_name, cp.handle
            FROM creator_verifications v
            JOIN users u ON u.id = v.user_id
            LEFT JOIN creator_profiles cp ON cp.user_id = v.user_id
            WHERE v.status = 'pending'
            ORDER BY v.created_at ASC
            LIMIT $1 OFFSET $2
            """,
            max(1, min(limit, 100)),
            max(0, offset),
        )
        return [dict(row) for row in rows]

    async def decide_verification(
        self,
        verification_id: UUID | str,
        *,
        status: str,
        reviewer_id: UUID | str | None,
        reason: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            UPDATE creator_verifications
            SET status = $2,
                reviewer_id = $3,
                reviewed_at = NOW(),
                reason = $4,
                expires_at = COALESCE($5, expires_at)
            WHERE id = $1
            RETURNING *
            """,
            verification_id,
            status,
            reviewer_id,
            reason,
            expires_at,
        )
        return dict(row) if row else {}

    async def get_verification(self, verification_id: UUID | str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            "SELECT * FROM creator_verifications WHERE id = $1", verification_id
        )
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Badges
    # ------------------------------------------------------------------
    async def list_active_badges(self, user_id: UUID | str) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM creator_badges
            WHERE user_id = $1
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY granted_at DESC
            """,
            user_id,
        )
        return [dict(row) for row in rows]

    async def grant_badge(
        self,
        *,
        user_id: UUID | str,
        badge: str,
        granted_by: UUID | str | None,
        expires_at: datetime | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_badges (user_id, badge, granted_by, expires_at, reason)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, badge) WHERE revoked_at IS NULL
            DO UPDATE SET
                granted_by = EXCLUDED.granted_by,
                granted_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                reason = EXCLUDED.reason
            RETURNING *
            """,
            user_id,
            badge,
            granted_by,
            expires_at,
            reason,
        )
        return dict(row)

    async def revoke_badge(
        self,
        *,
        user_id: UUID | str,
        badge: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            UPDATE creator_badges
            SET revoked_at = NOW(), reason = COALESCE($3, reason)
            WHERE user_id = $1 AND badge = $2 AND revoked_at IS NULL
            RETURNING *
            """,
            user_id,
            badge,
            reason,
        )
        return dict(row) if row else {}

    # ------------------------------------------------------------------
    # Profile tier
    # ------------------------------------------------------------------
    async def set_profile_tier(
        self,
        user_id: UUID | str,
        *,
        tier: str,
        verified_at: datetime | None = None,
        verification_expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            UPDATE creator_profiles
            SET tier = $2,
                verified_at = $3,
                verification_expires_at = $4,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            tier,
            verified_at,
            verification_expires_at,
        )
        return dict(row) if row else {}
