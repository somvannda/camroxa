"""CutLuy payment service for Cambodia KHQR payments."""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import uuid4

import httpx

from platform_api.services.cutluy_webhook import verify_cutluy_webhook_signature

logger = logging.getLogger(__name__)

_PAID_STATUSES = {"paid", "completed", "approved", "succeeded", "success"}
_FAILED_STATUSES = {"failed", "cancelled", "canceled", "declined"}
_EXPIRED_STATUSES = {"expired"}


def normalize_cutluy_payment_status(raw: Any) -> str:
    """Map a CutLuy payment status string onto paid | failed | expired | pending."""
    value = str(raw or "").strip().lower()
    if value in _PAID_STATUSES:
        return "paid"
    if value in _FAILED_STATUSES:
        return "failed"
    if value in _EXPIRED_STATUSES:
        return "expired"
    return "pending"


class CutLuyService:
    """Service for CutLuy payment integration (cutluy.com).

    Uses the same `/v1/payments` API as desktop billing checkout.
    """

    def __init__(self) -> None:
        from platform_api.config import get_settings

        settings = get_settings()
        self._api_key = (settings.cutluy_secret_key or "").strip()
        self._webhook_secret = (settings.cutluy_webhook_secret or "").strip()
        base = (settings.cutluy_api_base_url or "https://cutluy.com").rstrip("/")
        self._api_url = base if base.endswith("/v1") else f"{base}/v1"

        if not self._api_key:
            logger.warning("PLATFORM_CUTLUY_SECRET_KEY not set")
        if not self._webhook_secret:
            logger.warning("PLATFORM_CUTLUY_WEBHOOK_SECRET not set")

    async def _resolve_config(self, db: Any | None = None) -> tuple[str, str, str | None]:
        """Return (api_base_url, secret_key, payment_link_id)."""
        if db is not None:
            from platform_api.services.billing_config_service import resolve_cutluy_config

            pool = getattr(db, "_pool", db)
            cutluy = await resolve_cutluy_config(pool)
            api_key = (cutluy.secret_key or "").strip()
            if not api_key:
                raise ValueError("CutLuy API key not configured")
            return cutluy.api_base_url.rstrip("/"), api_key, cutluy.payment_link_id

        if not self._api_key:
            raise ValueError("CutLuy API key not configured")
        base = self._api_url.removesuffix("/v1")
        return base, self._api_key, None

    async def _create_payment(
        self,
        *,
        amount_cents: int,
        reference_id: str,
        metadata: dict[str, Any],
        db: Any | None = None,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        api_base_url, api_key, _payment_link_id = await self._resolve_config(db)
        payload: dict[str, Any] = {
            "amount": round(amount_cents / 100, 2),
            "reference_id": reference_id,
            "metadata": metadata,
            "idempotency_key": reference_id,
        }
        if success_url:
            payload["success_url"] = success_url
        if cancel_url:
            payload["cancel_url"] = cancel_url
        # Web music owns the post-pay UX. Do not attach the portal/desktop
        # payment_link_id — that hosted page redirects into onboarding.

        url = f"{api_base_url}/v1/payments"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 400 and (
                    "success_url" in payload or "cancel_url" in payload
                ):
                    payload.pop("success_url", None)
                    payload.pop("cancel_url", None)
                    response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                payment = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "CutLuy API error: %s - %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise ValueError(f"Payment creation failed: {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("CutLuy unexpected error: %s", exc)
            raise

        checkout_url = payment.get("checkout_url") or payment.get("url")
        if not checkout_url:
            raise ValueError("CutLuy did not return a checkout URL")

        return {
            "checkout_url": checkout_url,
            "payment_id": payment.get("id"),
            "expires_at": payment.get("expires_at"),
        }

    async def create_subscription_payment(
        self,
        user_id: str,
        plan_name: str,
        amount_cents: int,
        billing_cycle: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[dict[str, Any]] = None,
        db: Any | None = None,
    ) -> dict[str, Any]:
        reference_id = f"camxora:web_sub:{user_id}:{uuid4().hex[:12]}"
        merged_metadata = {
            **(metadata or {}),
            "user_id": user_id,
            "plan_name": plan_name,
            "billing_cycle": billing_cycle,
            "type": "subscription",
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        return await self._create_payment(
            amount_cents=amount_cents,
            reference_id=reference_id,
            metadata=merged_metadata,
            db=db,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    async def create_topup_payment(
        self,
        user_id: str,
        pack_name: str,
        amount_cents: int,
        credits: int,
        success_url: str,
        cancel_url: str,
        metadata: Optional[dict[str, Any]] = None,
        db: Any | None = None,
    ) -> dict[str, Any]:
        reference_id = f"camxora:web_topup:{user_id}:{uuid4().hex[:12]}"
        merged_metadata = {
            **(metadata or {}),
            "user_id": user_id,
            "pack_name": pack_name,
            "credits": credits,
            "type": "topup",
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        return await self._create_payment(
            amount_cents=amount_cents,
            reference_id=reference_id,
            metadata=merged_metadata,
            db=db,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        if not self._webhook_secret:
            logger.error("Cannot verify webhook - secret not configured")
            return False

        return verify_cutluy_webhook_signature(
            raw_body=body,
            signature_header=signature,
            secret=self._webhook_secret,
            max_age_seconds=300,
        )

    async def get_payment_status(self, payment_id: str, db: Any | None = None) -> dict[str, Any]:
        api_base_url, api_key, _payment_link_id = await self._resolve_config(db)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{api_base_url}/v1/payments/{payment_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("CutLuy API error: %s", exc.response.status_code)
            raise ValueError(f"Failed to get payment status: {exc.response.status_code}") from exc

    async def cancel_subscription(self, subscription_id: str) -> bool:
        if not self._api_key:
            raise ValueError("CutLuy API key not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._api_url}/subscriptions/{subscription_id}/cancel",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as exc:
            logger.error("CutLuy cancel subscription error: %s", exc.response.status_code)
            return False
        except Exception as exc:
            logger.error("CutLuy unexpected error: %s", exc)
            return False


_cutluy_service: Optional[CutLuyService] = None


def get_cutluy_service() -> CutLuyService:
    global _cutluy_service
    if _cutluy_service is None:
        _cutluy_service = CutLuyService()
    return _cutluy_service
