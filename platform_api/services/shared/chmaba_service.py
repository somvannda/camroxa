"""ChmabaPay (KHQR / ABA PayWay) payment service.

ChmabaPay never holds funds: money settles straight into the store's own ABA
PayWay link. There is no sandbox, so every key is live and a payment is only
treated as paid after a signature-verified webhook or an authoritative
``check-status`` read.

This mirrors the contract already running on the musicapi service:

* ``POST   /v1/payments``                          → mint a KHQR payment
* ``GET    /v1/transactions/check-status/{id}``    → authoritative status
* ``GET    /v1/khqr/render.svg?payload=…``         → public QR renderer
* ``POST   {webhook}`` with ``X-ChmabaPay-Signature`` and ``X-ChmabaPay-Event``
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from platform_api.services.billing_config_service import (
    ChmabaConfig,
    resolve_chmaba_config,
)
from platform_api.services.chmaba_webhook import verify_chmaba_webhook_signature
from platform_api.services.shared.cutluy_service import extract_cutluy_qr_string
from platform_api.services.v2.payment_security import (
    require_chmaba_checkout_url,
    validate_payment_id,
)

logger = logging.getLogger(__name__)

_PAID_STATUSES = {"paid", "completed", "approved", "succeeded", "success"}
_FAILED_STATUSES = {"failed", "cancelled", "canceled", "declined"}
_EXPIRED_STATUSES = {"expired"}

REQUEST_TIMEOUT_SECONDS = 30.0


class ChmabaConfigurationError(ValueError):
    """Raised when the live key or store pointer is missing."""


class ChmabaAPIError(RuntimeError):
    """Raised when ChmabaPay answers with an error or times out."""

    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


def extract_chmaba_qr_string(payload: Any) -> str | None:
    """Return the Bakong KHQR EMV payload from a ChmabaPay payment object."""
    # A KHQR payload is provider-agnostic (it always starts with `000201`), so
    # the CutLuy extractor scans exactly the same keys and nested envelopes.
    return extract_cutluy_qr_string(payload)


def normalize_chmaba_payment_status(raw: Any) -> str:
    """Map a ChmabaPay status string onto paid | failed | expired | pending.

    ChmabaPay reports upper-case states (``PAID``/``FAILED``) on the
    check-status endpoint while the create call uses lower-case, so both are
    normalised here rather than at every call site.
    """
    value = str(raw or "").strip().lower()
    if value in _PAID_STATUSES:
        return "paid"
    if value in _FAILED_STATUSES:
        return "failed"
    if value in _EXPIRED_STATUSES:
        return "expired"
    return "pending"


def _flatten(payload: Any) -> dict[str, Any]:
    """Merge a possible ``{"data": {...}}`` envelope into one dict."""
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("data")
    if isinstance(nested, dict):
        return {**payload, **nested}
    return payload


class ChmabaService:
    """Thin ChmabaPay REST client with DB-resolved credentials."""

    def __init__(
        self,
        *,
        api_base_url: str | None = None,
        api_key: str | None = None,
        store_id: str | None = None,
        webhook_secret: str | None = None,
    ) -> None:
        self._api_base_url = (api_base_url or "").rstrip("/") or None
        self._api_key = (api_key or "").strip() or None
        self._store_id = (store_id or "").strip() or None
        self._webhook_secret = (webhook_secret or "").strip() or None

    async def _resolve(self, db: Any | None = None) -> ChmabaConfig:
        """Return credentials — admin-managed DB settings override env vars."""
        if db is None:
            from platform_api.config import get_settings

            settings = get_settings()
            env_api_key = (getattr(settings, "chmaba_api_key", "") or "").strip()
            env_store_id = (getattr(settings, "chmaba_store_id", "") or "").strip()
            env_webhook_secret = (
                getattr(settings, "chmaba_webhook_secret", "") or ""
            ).strip()
            api_key = self._api_key or env_api_key
            store_id = self._store_id or env_store_id
            webhook_secret = self._webhook_secret or env_webhook_secret
            return ChmabaConfig(
                api_base_url=(
                    self._api_base_url
                    or getattr(settings, "chmaba_api_base_url", "")
                    or "https://pay.chmaba.com"
                ).rstrip("/"),
                api_key=api_key,
                store_id=store_id,
                api_key_source="environment" if api_key else "none",
                webhook_secret=webhook_secret,
                webhook_secret_source="environment" if webhook_secret else "none",
                store_source="environment" if store_id else "none",
            )

        pool = getattr(db, "_pool", db)
        config = await resolve_chmaba_config(pool)
        # Explicit constructor values (tests, one-off scripts) win over both.
        return ChmabaConfig(
            api_base_url=(self._api_base_url or config.api_base_url).rstrip("/"),
            api_key=self._api_key or config.api_key,
            store_id=self._store_id or config.store_id,
            api_key_source=config.api_key_source,
            webhook_secret=self._webhook_secret or config.webhook_secret,
            webhook_secret_source=config.webhook_secret_source,
            store_source=config.store_source,
        )

    async def _request(
        self,
        config: ChmabaConfig,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{config.api_base_url}{path}"
        headers = {"Authorization": f"Bearer {config.api_key}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0)
            ) as client:
                response = await client.request(method, url, headers=headers, json=body)
        except httpx.RequestError as exc:
            logger.error("ChmabaPay request failed: %s", exc)
            raise ChmabaAPIError(
                "Payment provider is unreachable. Please try again.",
                retryable=True,
            ) from exc

        text = response.text
        try:
            payload = response.json() if text else None
        except ValueError:
            payload = None

        if response.status_code >= 400:
            logger.error(
                "ChmabaPay API error: %s - %s",
                response.status_code,
                text[:300],
            )
            raise ChmabaAPIError(
                f"Payment provider error ({response.status_code}).",
                retryable=response.status_code >= 500,
                status_code=response.status_code,
            )
        return payload

    async def create_payment(
        self,
        *,
        amount_cents: int,
        reference_id: str,
        metadata: dict[str, Any] | None = None,
        db: Any | None = None,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        """Mint a payment and return checkout_url/payment_id/qr_string/expires_at.

        ``reference_id`` is echoed back by the provider and is the only field
        used to map a webhook to a local row, so callers must store it.
        """
        config = await self._resolve(db)
        if not config.configured:
            raise ChmabaConfigurationError(
                "ChmabaPay billing is not configured yet. Add the API key and "
                "store id in Admin Settings → Payment."
            )

        body: dict[str, Any] = {
            "amount": round(int(amount_cents) / 100, 2),
            "reference_id": reference_id,
            "idempotency_key": reference_id,
            "store": config.store_id,
            "metadata": {**(metadata or {}), "provider": "chmaba"},
        }
        # ChmabaPay drives the post-pay UX itself (the KHQR modal polls our own
        # status route), so redirect URLs are informational only.
        if success_url:
            body["success_url"] = success_url
        if cancel_url:
            body["cancel_url"] = cancel_url

        payload = _flatten(
            await self._request(config, "/v1/payments", method="POST", body=body)
        )
        payment_id = validate_payment_id(str(payload.get("id") or payload.get("payment_id") or ""))

        checkout_raw = payload.get("checkout_url") or payload.get("url")
        checkout_url = (
            require_chmaba_checkout_url(str(checkout_raw), api_base_url=config.api_base_url)
            if checkout_raw
            else f"{config.api_base_url}/pay/{payment_id}"
        )

        expires_raw = payload.get("expires_at")
        return {
            "checkout_url": checkout_url,
            "payment_id": payment_id,
            "expires_at": "" if expires_raw is None else str(expires_raw),
            "qr_string": extract_chmaba_qr_string(payload) or "",
            "provider": "chmaba",
            "status": normalize_chmaba_payment_status(payload.get("status")),
        }

    async def get_payment_status(
        self,
        payment_id: str,
        db: Any | None = None,
    ) -> dict[str, Any]:
        """Read the authoritative status for a payment id."""
        safe_id = validate_payment_id(payment_id)
        config = await self._resolve(db)
        if not config.api_key:
            raise ChmabaConfigurationError("ChmabaPay API key is not configured.")
        payload = _flatten(
            await self._request(
                config,
                f"/v1/transactions/check-status/{safe_id}",
            )
        )
        return payload

    async def verify_webhook_signature_async(
        self,
        raw_body: bytes,
        signature: str,
        db: Any | None = None,
    ) -> bool:
        config = await self._resolve(db)
        return verify_chmaba_webhook_signature(
            raw_body=raw_body,
            signature_header=signature,
            secret=config.webhook_secret,
        )


_chmaba_service: Optional[ChmabaService] = None


def get_chmaba_service() -> ChmabaService:
    global _chmaba_service
    if _chmaba_service is None:
        _chmaba_service = ChmabaService()
    return _chmaba_service
