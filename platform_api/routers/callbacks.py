"""Callbacks router for external service notifications.

Provides the public Suno callback endpoint that replaces the Desktop_App's
local ngrok tunnel. This endpoint does NOT use JWT authentication — it validates
requests via HMAC signature and/or IP allowlist.

Requirements: 11.2, 11.3, 11.6, 11.8
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel

from platform_api.config import get_settings
from platform_api.models.enums import TaskStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/callbacks", tags=["callbacks"])


# ---------------------------------------------------------------------------
# Callback Payload Schema
# ---------------------------------------------------------------------------


class SunoCallbackPayload(BaseModel):
    """Expected payload from the Suno callback notification.

    Fields are kept flexible with optional values to handle various
    notification formats from Suno.
    """

    task_id: str | None = None
    taskId: str | None = None  # Alternative casing from Suno API
    status: str | None = None
    audio_url: str | None = None
    audio_url_ok: str | None = None
    audio_url_alt: str | None = None
    data: dict[str, Any] | None = None  # Nested payload variant


# ---------------------------------------------------------------------------
# Protocols for callback processing dependencies
# ---------------------------------------------------------------------------


class SunoTaskRepository(Protocol):
    """Protocol for Suno task lookup and update during callback processing."""

    async def find_by_external_id(self, external_task_id: str) -> dict | None:
        """Find a Suno task by its external (Suno-assigned) task ID.

        Returns:
            Dict with task fields or None if not found.
        """
        ...

    async def update_status(
        self,
        task_id: UUID,
        *,
        status: TaskStatus,
        audio_url_ok: str | None = None,
        audio_url_alt: str | None = None,
    ) -> None:
        """Update a Suno task's status and audio URLs."""
        ...


class NotificationPort(Protocol):
    """Protocol for pushing WebSocket notifications."""

    async def push(self, user_id: str, event: str, payload: dict) -> None:
        """Push a real-time notification to a user's connected clients."""
        ...

    async def queue(self, user_id: str, event: str, payload: dict) -> None:
        """Queue a notification for offline delivery."""
        ...


# ---------------------------------------------------------------------------
# Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_suno_task_repo() -> SunoTaskRepository:
    """Placeholder dependency for SunoTaskRepository — override via app.dependency_overrides."""
    raise NotImplementedError(
        "SunoTaskRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_notification_port() -> NotificationPort:
    """Placeholder dependency for NotificationPort — override via app.dependency_overrides."""
    raise NotImplementedError(
        "NotificationPort dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases
SunoTaskRepoDep = Annotated[SunoTaskRepository, Depends(_get_suno_task_repo)]
NotificationDep = Annotated[NotificationPort, Depends(_get_notification_port)]


# ---------------------------------------------------------------------------
# HMAC / IP Validation Helpers
# ---------------------------------------------------------------------------

# Allowed IP ranges for Suno callbacks (configurable via settings in production)
_SUNO_ALLOWED_IPS: set[str] = set()


def _validate_hmac_signature(
    body: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    """Validate HMAC-SHA256 signature of the request body.

    Args:
        body: Raw request body bytes.
        signature: The signature from the request header (hex-encoded).
        secret: The shared secret for HMAC computation.

    Returns:
        True if the signature is valid.
    """
    if not signature or not secret:
        return False

    expected = hmac.HMAC(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _validate_callback_request(
    client_ip: str | None,
    body: bytes,
    signature: str | None,
) -> bool:
    """Validate callback request via HMAC signature or IP allowlist.

    Returns True if either validation method succeeds.
    Falls back to accepting all requests if no HMAC secret is configured
    and no IP allowlist is set (development mode).
    """
    settings = get_settings()
    hmac_secret = getattr(settings, "suno_callback_hmac_secret", "")

    # Try HMAC validation first
    if hmac_secret and signature:
        if _validate_hmac_signature(body, signature, hmac_secret):
            return True

    # Try IP allowlist
    if _SUNO_ALLOWED_IPS and client_ip:
        if client_ip in _SUNO_ALLOWED_IPS:
            return True

    # Development fallback: accept if no security is configured
    if not hmac_secret and not _SUNO_ALLOWED_IPS:
        logger.warning(
            "Callback accepted without HMAC or IP validation (dev mode). "
            "Configure PLATFORM_SUNO_CALLBACK_HMAC_SECRET for production."
        )
        return True

    return False


# ---------------------------------------------------------------------------
# Callback Processing Logic
# ---------------------------------------------------------------------------


def _extract_task_id_from_payload(payload: SunoCallbackPayload) -> str | None:
    """Extract the Suno task ID from the callback payload.

    Handles multiple payload formats from Suno API.
    """
    # Direct task_id field
    if payload.task_id:
        return payload.task_id
    if payload.taskId:
        return payload.taskId

    # Nested in data field
    if payload.data and isinstance(payload.data, dict):
        return payload.data.get("task_id") or payload.data.get("taskId")

    return None


def _extract_status_from_payload(payload: SunoCallbackPayload) -> TaskStatus | None:
    """Map callback status string to TaskStatus enum."""
    status_str = payload.status
    if payload.data and isinstance(payload.data, dict):
        status_str = status_str or payload.data.get("status")

    if not status_str:
        return None

    status_upper = status_str.upper().strip()
    if status_upper in ("SUCCESS", "COMPLETE", "COMPLETED", "DONE"):
        return TaskStatus.SUCCESS
    elif status_upper in ("FAILED", "ERROR", "FAILURE"):
        return TaskStatus.FAILED
    return None


def _extract_audio_urls(payload: SunoCallbackPayload) -> tuple[str | None, str | None]:
    """Extract OK and Alt track audio URLs from the callback payload.

    Returns:
        Tuple of (audio_url_ok, audio_url_alt).
    """
    audio_ok = payload.audio_url_ok
    audio_alt = payload.audio_url_alt

    # Try nested data field
    if payload.data and isinstance(payload.data, dict):
        audio_ok = audio_ok or payload.data.get("audio_url_ok") or payload.data.get("audioUrlOk")
        audio_alt = audio_alt or payload.data.get("audio_url_alt") or payload.data.get("audioUrlAlt")

        # Single audio_url might be the OK track
        if not audio_ok and payload.data.get("audio_url"):
            audio_ok = payload.data["audio_url"]

    # Fallback to top-level audio_url as OK track
    if not audio_ok and payload.audio_url:
        audio_ok = payload.audio_url

    return audio_ok, audio_alt


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/suno",
    status_code=200,
    summary="Suno callback endpoint",
    include_in_schema=False,  # Internal callback, not shown in public docs
)
async def suno_callback(
    request: Request,
    task_repo: SunoTaskRepoDep,
    notification: NotificationDep,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> Response:
    """Receive and process Suno completion notifications.

    This endpoint replaces the Desktop_App's local ngrok callback (Req 11.2).
    No JWT authentication is required — validation is via HMAC/IP.

    Processing flow (Req 11.3):
    1. Validate request via HMAC signature or IP allowlist.
    2. Parse payload and extract task ID.
    3. Look up task in the database. Discard if unrecognized (Req 11.8).
    4. Update task status and store audio URLs (Req 11.6).
    5. Push WebSocket notification to the user (Req 11.3).
    """
    # Read raw body for HMAC validation
    body = await request.body()
    client_ip = request.client.host if request.client else None

    # --- HMAC / IP Validation ---
    if not _validate_callback_request(client_ip, body, x_signature):
        logger.warning(
            "Suno callback rejected: HMAC/IP validation failed. IP=%s",
            client_ip,
        )
        return Response(status_code=403, content="Forbidden")

    # --- Parse Payload ---
    try:
        import json as json_module

        raw_payload = json_module.loads(body)
        payload = SunoCallbackPayload(**raw_payload)
    except Exception as exc:
        # Malformed payload (Req 11.8)
        logger.warning(
            "Suno callback discarded: malformed payload. Error=%s",
            str(exc)[:200],
        )
        return Response(status_code=200, content="OK")

    # --- Extract Task ID ---
    external_task_id = _extract_task_id_from_payload(payload)
    if not external_task_id:
        # No task ID in payload (Req 11.8)
        logger.warning(
            "Suno callback discarded: no task_id found in payload."
        )
        return Response(status_code=200, content="OK")

    # --- Lookup Task ---
    task_data = await task_repo.find_by_external_id(external_task_id)
    if task_data is None:
        # Unrecognized task ID (Req 11.8)
        logger.warning(
            "Suno callback discarded: unrecognized task_id=%s",
            external_task_id,
        )
        return Response(status_code=200, content="OK")

    # --- Extract status and audio URLs ---
    new_status = _extract_status_from_payload(payload)
    if new_status is None:
        logger.warning(
            "Suno callback for task_id=%s: could not determine status. Ignoring.",
            external_task_id,
        )
        return Response(status_code=200, content="OK")

    audio_url_ok, audio_url_alt = _extract_audio_urls(payload)

    # --- Update Task Record (Req 11.3, 11.6) ---
    task_id = UUID(str(task_data["id"]))
    user_id = str(task_data["user_id"])

    await task_repo.update_status(
        task_id,
        status=new_status,
        audio_url_ok=audio_url_ok,
        audio_url_alt=audio_url_alt,
    )

    logger.info(
        "Suno callback processed: task_id=%s, external_id=%s, status=%s",
        task_id,
        external_task_id,
        new_status.value,
    )

    # --- Push WebSocket Notification (Req 11.3) ---
    notification_payload = {
        "task_id": str(task_id),
        "external_task_id": external_task_id,
        "status": new_status.value,
    }
    if new_status == TaskStatus.SUCCESS:
        notification_payload["audio_url_ok"] = audio_url_ok
        notification_payload["audio_url_alt"] = audio_url_alt

    try:
        await notification.push(
            user_id=user_id,
            event="suno_task_completed",
            payload=notification_payload,
        )
    except Exception as exc:
        # Non-critical: log but don't fail the callback
        logger.error(
            "Failed to push WebSocket notification for task %s: %s",
            task_id,
            str(exc)[:200],
        )
        # Queue for offline delivery
        try:
            await notification.queue(
                user_id=user_id,
                event="suno_task_completed",
                payload=notification_payload,
            )
        except Exception:
            logger.error(
                "Failed to queue notification for task %s",
                task_id,
            )

    return Response(status_code=200, content="OK")
