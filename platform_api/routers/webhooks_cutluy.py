"""CutLuy webhook handler for payment events."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from platform_api.services.v2.subscription_service import SubscriptionService
from platform_api.services.v2.topup_service import TopupService
from platform_api.exceptions import ValidationError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = logging.getLogger(__name__)


async def _get_subscription_service() -> SubscriptionService:
    raise NotImplementedError("SubscriptionService dependency not configured.")


async def _get_topup_service() -> TopupService:
    raise NotImplementedError("TopupService dependency not configured.")


class WebhookResponse(BaseModel):
    received: bool = True
    processed: bool = True
    message: str = "Webhook processed successfully"


@router.post("/cutluy", response_model=WebhookResponse, status_code=200)
async def cutluy_webhook(
    request: Request,
    x_cutluy_signature: str | None = Header(default=None),
    x_cutluy_event: str | None = Header(default=None),
) -> WebhookResponse:
    """Handle CutLuy payment webhook events."""
    body_bytes = await request.body()

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Failed to parse webhook JSON: %s", exc)
        raise ValidationError("Invalid JSON payload") from exc

    event_type = x_cutluy_event or payload.get("type", "unknown")
    metadata = payload.get("metadata") or payload.get("data", {}).get("metadata") or {}
    payment_type = metadata.get("type", "topup")

    logger.info("Received CutLuy webhook: %s (payment_type=%s)", event_type, payment_type)

    if event_type.startswith("subscription.") or payment_type == "subscription":
        subscription_service = await _get_subscription_service()
        result = await subscription_service.handle_cutluy_webhook(
            event_type=event_type,
            payload=payload,
            signature=x_cutluy_signature,
            raw_body=body_bytes,
        )
        return WebhookResponse(
            received=True,
            processed=result.get("processed", False),
            message=result.get("message", "Subscription webhook processed"),
        )

    if event_type in {"payment.completed", "payment.failed"}:
        if payment_type == "subscription":
            subscription_service = await _get_subscription_service()
            result = await subscription_service.handle_cutluy_webhook(
                event_type=event_type,
                payload=payload,
                signature=x_cutluy_signature,
                raw_body=body_bytes,
            )
        else:
            topup_service = await _get_topup_service()
            result = await topup_service.handle_topup_webhook(
                event_type=event_type,
                payload=payload,
                signature=x_cutluy_signature,
                raw_body=body_bytes,
            )

        return WebhookResponse(
            received=True,
            processed=result.get("processed", False),
            message=result.get("message", "Payment webhook processed"),
        )

    logger.warning("Unknown CutLuy webhook event type: %s", event_type)
    return WebhookResponse(
        received=True,
        processed=False,
        message=f"Unknown event type: {event_type}",
    )


@router.get("/cutluy/health")
async def webhook_health() -> dict[str, Any]:
    """Health check endpoint for CutLuy webhook delivery."""
    return {
        "status": "healthy",
        "service": "cutluy-webhook",
        "ready": True,
    }
