"""Creator payout readiness: KYC, payout accounts, earnings, and payouts."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from platform_api.exceptions import (
    DuplicateError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

MIN_PAYOUT_MICROS = 20_000_000
PAYOUT_RELEASE_ENABLED = True
KYC_ID_TYPES = {"passport", "national_id", "drivers_license"}
PAYOUT_METHODS = {"aba", "wing", "khqr", "bank", "paypal", "wise"}
CURRENCIES = {"USD", "KHR"}
TAX_FORMS = {"w9", "w8ben"}
DEFAULT_WITHHOLDING_BPS = 3000

# Cambodia has no US tax treaty, so every Cambodian creator pays the statutory
# 30% unless they are a US person filing a W-9. The product is Cambodia-only for
# now, so there is no treaty table to maintain.
USD_KHR_RATE = float(os.environ.get("CREATOR_USD_KHR_RATE", "4100"))

# The riel has traded in a narrow band for years. Anything outside this range is
# a typo (410 for 4100, or 41000) and would mispay every KHR creator at once.
KHR_RATE_MIN = 3500.0
KHR_RATE_MAX = 5000.0


def withholding_bps_for(tax_form: str | None, tax_country: str | None) -> int:
    """US royalties withholding rate, in basis points.

    A US person on a W-9 pays nothing up front. Everyone else — including every
    Cambodian creator — is withheld at the statutory 30%.
    """
    form = str(tax_form or "").strip().lower()
    country = str(tax_country or "").strip().upper()
    if form == "w9" and country == "US":
        return 0
    return DEFAULT_WITHHOLDING_BPS


def payout_minor_units(amount_micros: int, currency: str, fx_rate: float) -> int:
    """Amount to send, in the payout currency's smallest unit.

    USD is paid in cents, KHR in whole riel. The ledger stays in USD micros, so
    a KHR payout records the rate that was used alongside the amount.
    """
    micros = max(0, int(amount_micros or 0))
    if str(currency).strip().upper() == "KHR":
        return int(round((micros / 1_000_000) * float(fx_rate or 0)))
    return int(round(micros / 10_000))


def split_withholding(gross_micros: int, bps: int) -> tuple[int, int, int]:
    """Return ``(gross, withheld, net)`` micros for a withholding rate."""
    gross = max(0, int(gross_micros or 0))
    rate = max(0, min(DEFAULT_WITHHOLDING_BPS, int(bps or 0)))
    withheld = (gross * rate) // 10_000
    return gross, withheld, gross - withheld


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

    async def _audit(
        self,
        *,
        actor_id: str | None,
        action: str,
        subject_type: str,
        subject_id: str | None = None,
        creator_id: str | None = None,
        amount_micros: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Append one money action to the immutable trail.

        Never let a failed audit write stop a payout: the payout already
        happened, and losing the record is worse than a missing log line only
        if we silently swallow it — so failures are logged loudly instead.
        """
        try:
            await self._pool.execute(
                """
                INSERT INTO creator_money_audit (
                    actor_id, action, subject_type, subject_id,
                    creator_id, amount_micros, detail
                ) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
                """,
                actor_id,
                action,
                subject_type,
                subject_id,
                creator_id,
                amount_micros,
                json.dumps(detail or {}),
            )
        except Exception:
            logger.exception(
                "Failed to write creator money audit entry: action=%s subject=%s",
                action,
                subject_id,
            )

    async def list_audit(
        self, *, creator_id: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT a.*, u.email AS actor_email, c.email AS creator_email
            FROM creator_money_audit a
            LEFT JOIN users u ON u.id = a.actor_id
            LEFT JOIN users c ON c.id = a.creator_id
            WHERE ($1::uuid IS NULL OR a.creator_id = $1::uuid)
            ORDER BY a.created_at DESC
            LIMIT $2
            """,
            creator_id,
            max(1, min(limit, 200)),
        )
        return {"items": [dict(row) for row in rows]}

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
        tax_form = str(data.get("tax_form") or "").strip().lower() or None
        if tax_form is not None and tax_form not in TAX_FORMS:
            raise ValidationError(
                "Tax form must be w9 or w8ben.",
                details={"fields": {"tax_form": "invalid"}},
            )
        tax_country = str(data.get("tax_country") or country).strip().upper()[:2] or country
        withholding_bps = withholding_bps_for(tax_form, tax_country)
        id_document_type = (
            str(data.get("id_document_type") or "").strip()[:100]
            or "application/octet-stream"
        )
        selfie_type = str(data.get("selfie_type") or "").strip()[:100] or None
        # Anything uploaded through the API lands under creator/kyc/ and is
        # encrypted; only pre-encryption rows keep the legacy flag.
        documents_encrypted = document_ref.startswith("creator/kyc/")

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
                tax_form, tax_country, withholding_rate_bps,
                id_document_type, selfie_type, documents_encrypted,
                submitted_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'pending',$10,$11,$12,$13,$14,$15,NOW(),NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                legal_name = EXCLUDED.legal_name,
                date_of_birth = EXCLUDED.date_of_birth,
                country_code = EXCLUDED.country_code,
                id_type = EXCLUDED.id_type,
                id_last4 = EXCLUDED.id_last4,
                id_document_ref = EXCLUDED.id_document_ref,
                selfie_ref = EXCLUDED.selfie_ref,
                tax_id = EXCLUDED.tax_id,
                tax_form = EXCLUDED.tax_form,
                tax_country = EXCLUDED.tax_country,
                withholding_rate_bps = EXCLUDED.withholding_rate_bps,
                id_document_type = EXCLUDED.id_document_type,
                selfie_type = EXCLUDED.selfie_type,
                documents_encrypted = EXCLUDED.documents_encrypted,
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
            tax_form,
            tax_country,
            withholding_bps,
            id_document_type,
            selfie_type,
            documents_encrypted,
        )
        return {"kyc": dict(row)}

    async def upload_kyc_document(
        self,
        user_id: str,
        *,
        kind: str,
        content_type: str,
        data: bytes,
    ) -> dict[str, Any]:
        """Store an identity document in private storage and return its key.

        The returned key is what the creator submits as ``id_document_ref`` or
        ``selfie_ref``. It is never a public URL.
        """
        if kind not in {"id", "selfie"}:
            raise ValidationError(
                "kind must be id or selfie.",
                details={"fields": {"kind": "invalid"}},
            )
        normalized = str(content_type or "").split(";")[0].strip().lower()
        if not (normalized.startswith("image/") or normalized == "application/pdf"):
            raise ValidationError(
                "Upload a photo or PDF of the document.",
                details={"fields": {"file": "image or PDF required"}},
            )
        if not data:
            raise ValidationError(
                "The uploaded document is empty.",
                details={"fields": {"file": "empty"}},
            )
        if len(data) > 10 * 1024 * 1024:
            raise ValidationError(
                "Documents are limited to 10 MB.",
                details={"fields": {"file": "max 10 MB"}},
            )

        from platform_api.services.storage_service import StorageService
        from platform_api.services.streaming_config_service import (
            resolve_streaming_storage_config,
        )

        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            raise ExternalServiceError(
                "Document uploads are not configured.",
                is_retryable=False,
                details={"reason": "storage_not_configured"},
            )
        extension = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/heic": "heic",
            "application/pdf": "pdf",
        }.get(normalized, "bin")
        key = f"creator/kyc/{user_id}/{kind}-{uuid4()}.{extension}"
        try:
            from platform_api.services.document_encryption import (
                document_cipher_from_settings,
            )

            cipher = document_cipher_from_settings()
            payload = cipher.encrypt(data)
            storage = StorageService.from_config(config)
            # Stored as opaque bytes: a leaked object or a signed URL to it
            # returns ciphertext, never a viewable identity document.
            await storage.upload_bytes(
                key=key, data=payload, content_type="application/octet-stream"
            )
        except Exception as exc:
            raise ExternalServiceError(
                "Could not store the uploaded document.",
                is_retryable=True,
                details={"provider": "storage"},
            ) from exc
        return {"key": key, "kind": kind, "content_type": normalized, "encrypted": True}

    async def read_kyc_document(
        self, user_id: str, *, kind: str
    ) -> dict[str, Any]:
        """Decrypt and return a KYC document.

        Documents are never served by handing the browser a storage URL: the
        object is ciphertext, and the API is the only place it is decrypted.
        """
        if kind not in {"id", "selfie"}:
            raise ValidationError(
                "kind must be id or selfie.",
                details={"fields": {"kind": "invalid"}},
            )
        row = await self._pool.fetchrow(
            """
            SELECT id_document_ref, selfie_ref, id_document_type, selfie_type,
                   documents_encrypted
            FROM creator_kyc WHERE user_id = $1
            """,
            user_id,
        )
        if row is None:
            raise NotFoundError("KYC submission not found.")
        ref = row["id_document_ref"] if kind == "id" else row["selfie_ref"]
        if not ref:
            raise NotFoundError("No document uploaded for this check.")
        ref = str(ref).strip()
        if ref.lower().startswith(("http://", "https://")):
            raise ValidationError(
                "This legacy document reference cannot be served. Re-upload it.",
                details={"fields": {"document": "legacy reference"}},
            )

        from platform_api.services.storage_service import StorageService
        from platform_api.services.streaming_config_service import (
            resolve_streaming_storage_config,
        )

        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            raise ExternalServiceError(
                "Document storage is not configured.",
                is_retryable=False,
                details={"reason": "storage_not_configured"},
            )
        storage = StorageService.from_config(config)
        try:
            raw = await storage.download_bytes(ref)
        except Exception as exc:
            raise ExternalServiceError(
                "Could not read the stored document.",
                is_retryable=True,
                details={"provider": "storage"},
            ) from exc

        encrypted = bool(row.get("documents_encrypted"))
        if encrypted:
            from platform_api.services.document_encryption import (
                document_cipher_from_settings,
            )

            try:
                data = document_cipher_from_settings().decrypt(raw)
            except Exception as exc:
                raise ExternalServiceError(
                    "Could not decrypt the stored document.",
                    is_retryable=False,
                    details={"reason": "decrypt_failed"},
                ) from exc
        else:
            data = raw

        media_type = (
            row["id_document_type"] if kind == "id" else row["selfie_type"]
        ) or "application/octet-stream"
        return {
            "data": data,
            "media_type": str(media_type),
            "encrypted": encrypted,
        }

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
            SELECT method, currency FROM creator_payout_accounts
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
        kyc = await self._pool.fetchrow(
            "SELECT withholding_rate_bps FROM creator_kyc WHERE user_id = $1", user_id
        )
        bps = int(kyc.get("withholding_rate_bps") or 0) if kyc else 0
        gross, withheld, net = split_withholding(int(available), bps)
        currency = str(account.get("currency") or "USD").strip().upper()
        if currency not in CURRENCIES:
            currency = "USD"
        fx_rate = 1.0 if currency == "USD" else USD_KHR_RATE
        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_payouts (
                creator_id, period_start, period_end, amount_micros,
                currency, method, status, created_by,
                gross_micros, withheld_micros, fx_rate, payout_amount_minor
            ) VALUES ($1,$2,$3,$4,$5,$6,'requested',$1,$7,$8,$9,$10)
            RETURNING *
            """,
            user_id,
            today.replace(day=1),
            today,
            net,
            currency,
            account["method"],
            gross,
            withheld,
            fx_rate,
            payout_minor_units(net, currency, fx_rate),
        )
        return {"payout": dict(row)}

    async def create_run(
        self,
        *,
        period_start: date,
        period_end: date,
        created_by: str,
        fx_rate: float | None = None,
    ) -> dict[str, Any]:
        if period_end <= period_start:
            raise ValidationError(
                "period_end must be after period_start.",
                details={"fields": {"period_end": "invalid"}},
            )
        rows = await self._pool.fetch(
            """
            SELECT e.creator_id,
                   SUM(e.net_micros)::bigint AS amount_micros,
                   a.method,
                   a.currency,
                   COALESCE(k.withholding_rate_bps, 0) AS withholding_rate_bps
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
            GROUP BY e.creator_id, a.method, a.currency, k.withholding_rate_bps
            HAVING SUM(e.net_micros) >= $1
            """,
            MIN_PAYOUT_MICROS,
        )
        created = 0
        skipped = 0
        for row in rows:
            gross, withheld, net = split_withholding(
                int(row["amount_micros"]), int(row.get("withholding_rate_bps") or 0)
            )
            currency = str(row.get("currency") or "USD").strip().upper()
            if currency not in CURRENCIES:
                currency = "USD"
            rate = 1.0 if currency == "USD" else float(fx_rate or USD_KHR_RATE)
            if currency == "KHR" and not (KHR_RATE_MIN <= rate <= KHR_RATE_MAX):
                raise ValidationError(
                    f"The KHR rate must be between {KHR_RATE_MIN:.0f} and {KHR_RATE_MAX:.0f} per USD.",
                    details={"fields": {"fx_rate": "out of range"}},
                )
            payout_id = await self._pool.fetchval(
                """
                INSERT INTO creator_payouts (
                    creator_id, period_start, period_end, amount_micros,
                    currency, method, status, created_by,
                    gross_micros, withheld_micros, fx_rate, payout_amount_minor
                ) VALUES ($1,$2,$3,$4,$5,$6,'requested',$7,$8,$9,$10,$11)
                ON CONFLICT (creator_id, period_start, period_end) DO NOTHING
                RETURNING id
                """,
                row["creator_id"],
                period_start,
                period_end,
                net,
                currency,
                row["method"],
                created_by,
                gross,
                withheld,
                rate,
                payout_minor_units(net, currency, rate),
            )
            if payout_id:
                created += 1
            else:
                skipped += 1
        await self._audit(
            actor_id=created_by,
            action="payout_run_created",
            subject_type="payout_run",
            detail={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "fx_rate": float(fx_rate or USD_KHR_RATE),
                "created": created,
                "skipped": skipped,
                "eligible_creators": len(rows),
            },
        )
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "fx_rate": float(fx_rate or USD_KHR_RATE),
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

    async def generate_statements(self, year: int) -> dict[str, Any]:
        """Roll every paid payout in a tax year into one statement per creator."""
        if not 2000 <= int(year) <= 2100:
            raise ValidationError(
                "year is out of range.",
                details={"fields": {"year": "invalid"}},
            )
        rows = await self._pool.fetch(
            """
            SELECT creator_id,
                   SUM(gross_micros)::bigint AS gross_micros,
                   SUM(withheld_micros)::bigint AS withheld_micros,
                   SUM(amount_micros)::bigint AS net_micros,
                   COUNT(*)::int AS payout_count
            FROM creator_payouts
            WHERE status = 'paid'
              AND paid_at IS NOT NULL
              AND EXTRACT(YEAR FROM paid_at) = $1
            GROUP BY creator_id
            """,
            year,
        )
        generated = 0
        for row in rows:
            kyc = await self._pool.fetchrow(
                "SELECT tax_form, tax_country FROM creator_kyc WHERE user_id = $1",
                row["creator_id"],
            )
            await self._pool.execute(
                """
                INSERT INTO creator_tax_statements (
                    creator_id, tax_year, currency,
                    gross_micros, withheld_micros, net_micros,
                    payout_count, tax_form, tax_country, generated_at
                ) VALUES ($1,$2,'USD',$3,$4,$5,$6,$7,$8,NOW())
                ON CONFLICT (creator_id, tax_year) DO UPDATE SET
                    gross_micros = EXCLUDED.gross_micros,
                    withheld_micros = EXCLUDED.withheld_micros,
                    net_micros = EXCLUDED.net_micros,
                    payout_count = EXCLUDED.payout_count,
                    tax_form = EXCLUDED.tax_form,
                    tax_country = EXCLUDED.tax_country,
                    generated_at = NOW()
                """,
                row["creator_id"],
                year,
                int(row["gross_micros"] or 0),
                int(row["withheld_micros"] or 0),
                int(row["net_micros"] or 0),
                int(row["payout_count"] or 0),
                kyc["tax_form"] if kyc else None,
                kyc["tax_country"] if kyc else None,
            )
            generated += 1
        return {"year": year, "creators": len(rows), "generated": generated}

    async def list_statements(
        self,
        *,
        user_id: str | None = None,
        year: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT s.*, u.email, u.display_name AS user_display_name, cp.handle
            FROM creator_tax_statements s
            JOIN users u ON u.id = s.creator_id
            LEFT JOIN creator_profiles cp ON cp.user_id = s.creator_id
            WHERE ($1::uuid IS NULL OR s.creator_id = $1::uuid)
              AND ($2::int IS NULL OR s.tax_year = $2::int)
            ORDER BY s.tax_year DESC, s.generated_at DESC
            LIMIT $3
            """,
            user_id,
            year,
            max(1, min(limit, 200)),
        )
        return {"items": [dict(row) for row in rows]}

    async def reconciliation(self) -> dict[str, Any]:
        """Compare creator earnings against payouts and flag any drift."""
        rows = await self._pool.fetch(
            """
            WITH earned AS (
                SELECT creator_id,
                       SUM(net_micros) FILTER (WHERE status IN ('available','paid'))::bigint AS earned_micros,
                       SUM(net_micros) FILTER (WHERE status = 'available')::bigint AS unpaid_micros,
                       SUM(net_micros) FILTER (WHERE status = 'paid')::bigint AS settled_micros
                FROM creator_earnings
                GROUP BY creator_id
            ),
            paid AS (
                SELECT creator_id,
                       SUM(amount_micros) FILTER (WHERE status = 'paid')::bigint AS paid_micros,
                       SUM(gross_micros) FILTER (WHERE status = 'paid')::bigint AS paid_gross_micros,
                       SUM(withheld_micros) FILTER (WHERE status = 'paid')::bigint AS withheld_micros,
                       SUM(amount_micros) FILTER (WHERE status IN ('requested','approved','processing'))::bigint AS in_flight_micros
                FROM creator_payouts
                GROUP BY creator_id
            ),
            creators AS (
                SELECT creator_id FROM earned
                UNION
                SELECT creator_id FROM paid
            )
            SELECT c.creator_id,
                   cp.handle,
                   u.email,
                   u.display_name AS user_display_name,
                   COALESCE(e.earned_micros, 0) AS earned_micros,
                   COALESCE(e.unpaid_micros, 0) AS unpaid_micros,
                   COALESCE(e.settled_micros, 0) AS settled_micros,
                   COALESCE(p.paid_micros, 0) AS paid_micros,
                   COALESCE(p.paid_gross_micros, 0) AS paid_gross_micros,
                   COALESCE(p.withheld_micros, 0) AS withheld_micros,
                   COALESCE(p.in_flight_micros, 0) AS in_flight_micros,
                   -- Compare like with like: earnings are pre-tax, so the payout gross
                   -- is the correct counterparty, not the netted amount.
                   (COALESCE(e.settled_micros, 0) - COALESCE(p.paid_gross_micros, 0)) AS variance_micros
            FROM creators c
            JOIN users u ON u.id = c.creator_id
            LEFT JOIN creator_profiles cp ON cp.user_id = c.creator_id
            LEFT JOIN earned e ON e.creator_id = c.creator_id
            LEFT JOIN paid p ON p.creator_id = c.creator_id
            ORDER BY ABS(COALESCE(e.settled_micros, 0) - COALESCE(p.paid_gross_micros, 0)) DESC,
                     u.display_name
            LIMIT 200
            """
        )
        items = [dict(row) for row in rows]
        totals = {
            "earned_micros": sum(int(row["earned_micros"] or 0) for row in items),
            "unpaid_micros": sum(int(row["unpaid_micros"] or 0) for row in items),
            "settled_micros": sum(int(row["settled_micros"] or 0) for row in items),
            "paid_micros": sum(int(row["paid_micros"] or 0) for row in items),
            "paid_gross_micros": sum(
                int(row.get("paid_gross_micros") or 0) for row in items
            ),
            "withheld_micros": sum(int(row.get("withheld_micros") or 0) for row in items),
            "in_flight_micros": sum(int(row["in_flight_micros"] or 0) for row in items),
            "variance_micros": sum(int(row["variance_micros"] or 0) for row in items),
        }
        totals["balanced"] = totals["variance_micros"] == 0
        return {"items": items, "totals": totals}

    async def release_available_earnings(self) -> int:
        result = await self._pool.execute(
            """
            UPDATE creator_earnings
            SET status = 'available'
            WHERE status = 'pending'
              AND available_at IS NOT NULL
              AND available_at <= NOW()
            """
        )
        try:
            return int(str(result).split()[-1])
        except (IndexError, ValueError):
            return 0

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
        await self._audit(
            actor_id=reviewer_id,
            action=f"kyc_{decision}",
            subject_type="creator_kyc",
            subject_id=user_id,
            creator_id=user_id,
            detail={"reason": reason or None},
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

    async def approve_payout(self, payout_id: str, *, reviewer_id: str) -> dict[str, Any]:
        payout = await self._pool.fetchrow(
            "SELECT * FROM creator_payouts WHERE id = $1", payout_id
        )
        if payout is None:
            raise NotFoundError("Payout not found.")
        if payout["status"] != "requested":
            raise ValidationError(
                "Only requested payouts can be approved.",
                details={"fields": {"status": "invalid"}},
            )
        if payout.get("created_by") and str(payout["created_by"]) == str(reviewer_id):
            raise ValidationError(
                "Maker-checker: the person who created the payout cannot approve it.",
                details={"fields": {"approval": "different reviewer required"}},
            )
        row = await self._pool.fetchrow(
            """
            UPDATE creator_payouts
            SET status = 'approved', approved_by = $2, approved_at = NOW()
            WHERE id = $1 AND status = 'requested'
            RETURNING *
            """,
            payout_id,
            reviewer_id,
        )
        await self._audit(
            actor_id=reviewer_id,
            action="payout_approved",
            subject_type="creator_payout",
            subject_id=str(payout_id),
            creator_id=str(payout["creator_id"]),
            amount_micros=int(payout["amount_micros"]),
            detail={"currency": payout.get("currency")},
        )
        return {"payout": dict(row)}

    async def mark_paid(self, payout_id: str, *, reference: str, reviewer_id: str) -> dict[str, Any]:
        payout = await self._pool.fetchrow(
            "SELECT * FROM creator_payouts WHERE id = $1", payout_id
        )
        if payout is None:
            raise NotFoundError("Payout not found.")
        if payout["status"] != "approved":
            raise ValidationError(
                "Payout must be approved before it can be marked paid.",
                details={"fields": {"status": "approval required"}},
            )
        if payout.get("approved_by") and str(payout["approved_by"]) == str(reviewer_id):
            raise ValidationError(
                "Maker-checker: the approver cannot mark the same payout paid.",
                details={"fields": {"payment": "different reviewer required"}},
            )
        if payout.get("created_by") and str(payout["created_by"]) == str(reviewer_id):
            raise ValidationError(
                "Maker-checker: the person who created the payout cannot mark it paid.",
                details={"fields": {"payment": "different reviewer required"}},
            )
        if not reference.strip():
            raise ValidationError(
                "A payment reference is required.",
                details={"fields": {"reference": "required"}},
            )
        row = await self._pool.fetchrow(
            """
            UPDATE creator_payouts
            SET status = 'paid', paid_at = NOW(), payment_ref = $2
            WHERE id = $1
            RETURNING *
            """,
            payout_id,
            reference.strip(),
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
        await self._audit(
            actor_id=reviewer_id,
            action="payout_paid",
            subject_type="creator_payout",
            subject_id=str(payout_id),
            creator_id=str(payout["creator_id"]),
            amount_micros=int(payout["amount_micros"]),
            detail={
                "reference": reference.strip(),
                "currency": payout.get("currency"),
                "withheld_micros": int(payout.get("withheld_micros") or 0),
            },
        )
        return {"payout": dict(row)}


async def run_earnings_release_loop(
    pool: Any,
    *,
    interval_seconds: int = 3600,
    startup_delay: float = 60.0,
) -> None:
    """Promote pending earnings to available once their holdback passes."""
    if startup_delay:
        await asyncio.sleep(startup_delay)
    service = CreatorPayoutService(pool)
    while True:
        try:
            released = await service.release_available_earnings()
            if released:
                logger.info("Released %s creator earnings rows.", released)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Creator earnings release failed; retrying next interval.")
        await asyncio.sleep(max(300, interval_seconds))
