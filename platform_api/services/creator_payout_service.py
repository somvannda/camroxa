"""Creator payout readiness: KYC, payout accounts, earnings, and payouts."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError

MIN_PAYOUT_MICROS = 20_000_000
KYC_ID_TYPES = {"passport", "national_id", "drivers_license"}
PAYOUT_METHODS = {"aba", "wing", "khqr", "bank", "paypal", "wise"}
CURRENCIES = {"USD", "KHR"}


def _micros_to_usd(micros: int) -> float:
    return round(int(micros or 0) / 1_000_000, 2)


def _age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _row(row: Any) -> dict[str, Any] | None:
    return dict(row) if row else None


class CreatorPayoutService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def _notify(self, user_id: Any, event_type: str, payload: dict[str, Any]) -> None:
        await self._pool.execute(
            """
            INSERT INTO notification_queue (user_id, event_type, payload, expires_at)
            VALUES ($1, $2, $3::jsonb, NOW() + INTERVAL '30 days')
            """,
            user_id,
            event_type,
            json.dumps(payload),
        )

    async def get_status(self, user_id: str) -> dict[str, Any]:
        kyc = await self._pool.fetchrow(
            "SELECT * FROM creator_kyc WHERE user_id = $1", user_id
        )
        account = await self._pool.fetchrow(
            """
            SELECT * FROM creator_payout_accounts
            WHERE user_id = $1 AND is_default
            LIMIT 1
            """,
            user_id,
        )
        balances = await self._pool.fetchrow(
            """
            SELECT
              COALESCE(SUM(net_micros) FILTER (WHERE status = 'available'), 0)::bigint AS available_micros,
              COALESCE(SUM(net_micros) FILTER (WHERE status IN ('pending','held')), 0)::bigint AS pending_micros,
              COALESCE(SUM(net_micros) FILTER (WHERE status = 'paid'), 0)::bigint AS paid_micros
            FROM creator_earnings
            WHERE creator_id = $1
            """,
            user_id,
        )
        payouts = await self._pool.fetch(
            """
            SELECT * FROM creator_payouts
            WHERE creator_id = $1
            ORDER BY created_at DESC
            LIMIT 20
            """,
            user_id,
        )
        available = int((balances or {})["available_micros"] or 0)
        return {
            "kyc": _row(kyc),
            "account": _row(account),
            "balance": {
                "available_micros": available,
                "available_usd": _micros_to_usd(available),
                "pending_micros": int((balances or {})["pending_micros"] or 0),
                "paid_micros": int((balances or {})["paid_micros"] or 0),
                "min_payout_micros": MIN_PAYOUT_MICROS,
            },
            "payouts": [dict(row) for row in payouts],
        }

    async def submit_kyc(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        legal_name = str(data.get("legal_name") or "").strip()
        if not 2 <= len(legal_name) <= 120:
            raise ValidationError(
                "Legal name is required.",
                details={"fields": {"legal_name": "2-120 characters"}},
            )
        try:
            dob = date.fromisoformat(str(data.get("date_of_birth") or ""))
        except ValueError as exc:
            raise ValidationError(
                "Date of birth is required (YYYY-MM-DD).",
                details={"fields": {"date_of_birth": "invalid date"}},
            ) from exc
        if _age(dob) < 18:
            raise ValidationError(
                "You must be 18 or older for payouts.",
                details={"fields": {"date_of_birth": "must be 18+"}},
            )
        country = str(data.get("country_code") or "").strip().upper()
        if len(country) != 2 or not country.isalpha():
            raise ValidationError(
                "Country code is required.",
                details={"fields": {"country_code": "2 letters"}},
            )
        id_type = str(data.get("id_type") or "").strip().lower()
        if id_type not in KYC_ID_TYPES:
            raise ValidationError(
                "ID type must be passport, national_id, or drivers_license.",
                details={"fields": {"id_type": "invalid"}},
            )
        id_last4 = str(data.get("id_last4") or "").strip()
        if len(id_last4) != 4:
            raise ValidationError(
                "Enter the last 4 characters of your ID.",
                details={"fields": {"id_last4": "4 characters"}},
            )
        document_ref = str(data.get("id_document_ref") or "").strip()
        if not document_ref:
            raise ValidationError(
                "ID document reference is required.",
                details={"fields": {"id_document_ref": "required"}},
            )
        selfie_ref = str(data.get("selfie_ref") or "").strip() or None
        tax_id = str(data.get("tax_id") or "").strip()[:40] or None

        existing = await self._pool.fetchrow(
            "SELECT status FROM creator_kyc WHERE user_id = $1", user_id
        )
        if existing and existing["status"] == "verified":
            raise DuplicateError("Payout verification is already approved.")

        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_kyc (
                user_id, legal_name, date_of_birth, country_code, id_type,
                id_last4, id_document_ref, selfie_ref, tax_id, status,
                submitted_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'pending',NOW(),NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                legal_name = EXCLUDED.legal_name,
                date_of_birth = EXCLUDED.date_of_birth,
                country_code = EXCLUDED.country_code,
                id_type = EXCLUDED.id_type,
                id_last4 = EXCLUDED.id_last4,
                id_document_ref = EXCLUDED.id_document_ref,
                selfie_ref = EXCLUDED.selfie_ref,
                tax_id = EXCLUDED.tax_id,
                status = 'pending',
                submitted_at = NOW(),
                reviewed_by = NULL,
                reviewed_at = NULL,
                reason = NULL,
                updated_at = NOW()
            RETURNING *
            """,
            user_id,
            legal_name,
            dob,
            country,
            id_type,
            id_last4,
            document_ref,
            selfie_ref,
            tax_id,
        )
        return {"kyc": dict(row)}

    async def upsert_payout_account(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        method = str(data.get("method") or "").strip().lower()
        if method not in PAYOUT_METHODS:
            raise ValidationError(
                "Unsupported payout method.",
                details={"fields": {"method": "invalid"}},
            )
        account_name = str(data.get("account_name") or "").strip()
        if not 2 <= len(account_name) <= 120:
            raise ValidationError(
                "Account name is required.",
                details={"fields": {"account_name": "2-120 characters"}},
            )
        last4 = str(data.get("account_last4") or "").strip()
        if len(last4) != 4:
            raise ValidationError(
                "Enter the last 4 characters of the account.",
                details={"fields": {"account_last4": "4 characters"}},
            )
        currency = str(data.get("currency") or "USD").strip().upper()
        if currency not in CURRENCIES:
            raise ValidationError(
                "Currency must be USD or KHR.",
                details={"fields": {"currency": "invalid"}},
            )
        bank_code = str(data.get("bank_code") or "").strip()[:30] or None

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE creator_payout_accounts SET is_default = FALSE, updated_at = NOW() WHERE user_id = $1",
                    user_id,
                )
                row = await conn.fetchrow(
                    """
                    INSERT INTO creator_payout_accounts (
                        user_id, method, account_name, account_last4, bank_code,
                        currency, status, is_default, updated_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,'pending',TRUE,NOW())
                    RETURNING *
                    """,
                    user_id,
                    method,
                    account_name,
                    last4,
                    bank_code,
                    currency,
                )
        return {"account": dict(row)}

    async def list_earnings(self, user_id: str) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM creator_earnings
            WHERE creator_id = $1
            ORDER BY created_at DESC
            LIMIT 100
            """,
            user_id,
        )
        return {"items": [dict(row) for row in rows]}

    async def request_payout(self, user_id: str) -> dict[str, Any]:
        kyc = await self._pool.fetchrow(
            "SELECT status FROM creator_kyc WHERE user_id = $1", user_id
        )
        if not kyc or kyc["status"] != "verified":
            raise ValidationError(
                "Complete payout verification first.",
                details={"fields": {"kyc": "required"}},
            )
        account = await self._pool.fetchrow(
            """
            SELECT method FROM creator_payout_accounts
            WHERE user_id = $1 AND is_default AND status = 'verified'
            LIMIT 1
            """,
            user_id,
        )
        if not account:
            raise ValidationError(
                "A verified payout account is required.",
                details={"fields": {"account": "required"}},
            )
        available = await self._pool.fetchval(
            """
            SELECT COALESCE(SUM(net_micros), 0)::bigint
            FROM creator_earnings
            WHERE creator_id = $1 AND status = 'available'
            """,
            user_id,
        )
        if int(available or 0) < MIN_PAYOUT_MICROS:
            raise ValidationError(
                "The minimum payout is $20.",
                details={"fields": {"balance": "below minimum"}},
            )
        pending = await self._pool.fetchval(
            """
            SELECT 1 FROM creator_payouts
            WHERE creator_id = $1 AND status IN ('requested','approved','processing')
            LIMIT 1
            """,
            user_id,
        )
        if pending:
            raise DuplicateError("A payout is already in progress.")

        today = date.today()
        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_payouts (
                creator_id, period_start, period_end, amount_micros,
                currency, method, status
            ) VALUES ($1,$2,$3,$4,'USD',$5,'requested')
            RETURNING *
            """,
            user_id,
            today.replace(day=1),
            today,
            int(available),
            account["method"],
        )
        return {"payout": dict(row)}

    async def create_run(self, *, period_start: date, period_end: date) -> dict[str, Any]:
        if period_end <= period_start:
            raise ValidationError(
                "period_end must be after period_start.",
                details={"fields": {"period_end": "invalid"}},
            )
        rows = await self._pool.fetch(
            """
            SELECT e.creator_id,
                   SUM(e.net_micros)::bigint AS amount_micros,
                   a.method
            FROM creator_earnings e
            JOIN creator_kyc k
              ON k.user_id = e.creator_id AND k.status = 'verified'
            JOIN creator_payout_accounts a
              ON a.user_id = e.creator_id AND a.is_default AND a.status = 'verified'
            WHERE e.status = 'available'
              AND NOT EXISTS (
                  SELECT 1 FROM creator_payouts p
                  WHERE p.creator_id = e.creator_id
                    AND p.status IN ('requested','approved','processing')
              )
            GROUP BY e.creator_id, a.method
            HAVING SUM(e.net_micros) >= $1
            """,
            MIN_PAYOUT_MICROS,
        )
        created = 0
        skipped = 0
        for row in rows:
            payout_id = await self._pool.fetchval(
                """
                INSERT INTO creator_payouts (
                    creator_id, period_start, period_end, amount_micros,
                    currency, method, status
                ) VALUES ($1,$2,$3,$4,'USD',$5,'requested')
                ON CONFLICT (creator_id, period_start, period_end) DO NOTHING
                RETURNING id
                """,
                row["creator_id"],
                period_start,
                period_end,
                int(row["amount_micros"]),
                row["method"],
            )
            if payout_id:
                created += 1
            else:
                skipped += 1
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "eligible_creators": len(rows),
            "created": created,
            "skipped": skipped,
        }

    async def export_rows(self, status: str | None = None) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT p.*, u.email, u.display_name AS user_display_name, cp.handle
            FROM creator_payouts p
            JOIN users u ON u.id = p.creator_id
            LEFT JOIN creator_profiles cp ON cp.user_id = p.creator_id
            WHERE ($1::text IS NULL OR p.status = $1)
            ORDER BY p.created_at DESC
            """,
            status,
        )
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    async def list_kyc(self, status: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT k.*, u.email, u.display_name AS user_display_name, cp.handle
            FROM creator_kyc k
            JOIN users u ON u.id = k.user_id
            LEFT JOIN creator_profiles cp ON cp.user_id = k.user_id
            WHERE ($1::text IS NULL OR k.status = $1)
            ORDER BY k.submitted_at DESC
            LIMIT $2 OFFSET $3
            """,
            status,
            max(1, min(limit, 100)),
            max(0, offset),
        )
        total = await self._pool.fetchval(
            "SELECT COUNT(*) FROM creator_kyc WHERE ($1::text IS NULL OR status = $1)",
            status,
        )
        return {"items": [dict(row) for row in rows], "total": int(total or 0), "limit": limit, "offset": offset}

    async def decide_kyc(
        self,
        user_id: str,
        *,
        decision: str,
        reviewer_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        if decision not in {"approve", "reject"}:
            raise ValidationError(
                "decision must be approve or reject.",
                details={"fields": {"decision": "invalid"}},
            )
        if decision == "reject" and not reason:
            raise ValidationError(
                "A reason is required when rejecting.",
                details={"fields": {"reason": "required"}},
            )
        expires = (
            datetime.now(timezone.utc) + timedelta(days=730)
            if decision == "approve"
            else None
        )
        row = await self._pool.fetchrow(
            """
            UPDATE creator_kyc
            SET status = $2, reviewed_by = $3, reviewed_at = NOW(),
                reason = $4, expires_at = $5, updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            "verified" if decision == "approve" else "rejected",
            reviewer_id,
            reason,
            expires,
        )
        if row is None:
            raise NotFoundError("KYC record not found.")
        if decision == "approve":
            await self._pool.execute(
                """
                UPDATE creator_earning_eligibility
                SET status = 'earning', earning_started_at = COALESCE(earning_started_at, NOW()), updated_at = NOW()
                WHERE creator_id = $1 AND status IN ('eligible','pending_verification')
                """,
                user_id,
            )
            await self._notify(
                user_id,
                "creator_payout_ready",
                {"payments_active": True},
            )
        return {"kyc": dict(row)}

    async def list_payouts(self, status: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT p.*, u.email, u.display_name AS user_display_name, cp.handle
            FROM creator_payouts p
            JOIN users u ON u.id = p.creator_id
            LEFT JOIN creator_profiles cp ON cp.user_id = p.creator_id
            WHERE ($1::text IS NULL OR p.status = $1)
            ORDER BY p.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            status,
            max(1, min(limit, 100)),
            max(0, offset),
        )
        total = await self._pool.fetchval(
            "SELECT COUNT(*) FROM creator_payouts WHERE ($1::text IS NULL OR status = $1)",
            status,
        )
        return {"items": [dict(row) for row in rows], "total": int(total or 0), "limit": limit, "offset": offset}

    async def mark_paid(self, payout_id: str, *, reference: str, reviewer_id: str) -> dict[str, Any]:
        payout = await self._pool.fetchrow(
            "SELECT * FROM creator_payouts WHERE id = $1", payout_id
        )
        if payout is None:
            raise NotFoundError("Payout not found.")
        if not reference.strip():
            raise ValidationError(
                "A payment reference is required.",
                details={"fields": {"reference": "required"}},
            )
        row = await self._pool.fetchrow(
            """
            UPDATE creator_payouts
            SET status = 'paid', paid_at = NOW(), payment_ref = $2,
                approved_by = COALESCE(approved_by, $3), approved_at = COALESCE(approved_at, NOW())
            WHERE id = $1
            RETURNING *
            """,
            payout_id,
            reference.strip(),
            reviewer_id,
        )
        await self._pool.execute(
            """
            UPDATE creator_earnings
            SET status = 'paid'
            WHERE creator_id = $1 AND status = 'available'
            """,
            payout["creator_id"],
        )
        await self._notify(
            payout["creator_id"],
            "creator_payout_paid",
            {
                "amount_micros": int(payout["amount_micros"]),
                "amount_usd": _micros_to_usd(int(payout["amount_micros"])),
                "reference": reference.strip(),
            },
        )
        return {"payout": dict(row)}
