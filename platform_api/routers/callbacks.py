"""Callbacks router for external service notifications.

Provides the public Suno callback endpoint that replaces the Desktop_App's
local ngrok tunnel. This endpoint does NOT use JWT authentication — it validates
requests via HMAC signature and/or IP allowlist.

Requirements: 11.2, 11.3, 11.6, 11.8
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from typing import Annotated, Any, Protocol
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel

from platform_api.config import get_settings
from platform_api.models.enums import TaskStatus
from platform_api.services.batch_service import BatchService
from platform_api.services.image_job_service import ImageJobService
from platform_api.services.image_job_runner import run_image_jobs_until_empty
from platform_api.services.suno_status_messages import (
    is_suno_failure_status,
    is_suno_success_status,
    suno_task_failure_message,
)

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
        error_message: str | None = None,
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


async def _get_batch_service() -> BatchService:
    """Placeholder dependency for BatchService callback handoff."""
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
    )

async def _get_image_job_service() -> ImageJobService:
    """Placeholder dependency for ImageJobService callback auto-run."""
    raise NotImplementedError(
        "ImageJobService dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases
SunoTaskRepoDep = Annotated[SunoTaskRepository, Depends(_get_suno_task_repo)]
NotificationDep = Annotated[NotificationPort, Depends(_get_notification_port)]
BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
ImageJobServiceDep = Annotated[ImageJobService, Depends(_get_image_job_service)]


# ---------------------------------------------------------------------------
# HMAC / IP Validation Helpers
# ---------------------------------------------------------------------------


def _configured_allowed_ips() -> set[str]:
    """Return the configured Suno callback IP allowlist (may be empty)."""
    settings = get_settings()
    raw = (getattr(settings, "suno_callback_allowed_ips", "") or "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


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

    # Accept either bare hex or sha256=<hex> forms.
    provided = signature.strip()
    if provided.lower().startswith("sha256="):
        provided = provided.split("=", 1)[1].strip()

    return hmac.compare_digest(expected, provided)


def _resolve_callback_client_ip(request: Request) -> str | None:
    """Extract client IP, honoring reverse-proxy X-Forwarded-For when present."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _extract_callback_signature(
    request: Request,
    x_signature: str | None,
) -> str | None:
    """Return the first non-empty Suno callback signature header value."""
    for candidate in (
        x_signature,
        request.headers.get("x-signature"),
        request.headers.get("X-Hmac-Signature"),
        request.headers.get("x-hmac-signature"),
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    return None


def _validate_callback_request(
    client_ip: str | None,
    body: bytes,
    signature: str | None,
) -> bool:
    """Validate callback request via HMAC (preferred) or IP allowlist.

    Security rules:
    - When a signature header is present, it must validate against the configured
      HMAC secret (fail closed on invalid/forged signatures).
    - Suno provider callbacks typically omit signatures; those are accepted.
    - Optional IP allowlist can additionally authorize callbacks behind nginx.
    - Open accept (no HMAC, no IP) only when ``debug=true``.
    """
    settings = get_settings()
    hmac_secret = (getattr(settings, "suno_callback_hmac_secret", "") or "").strip()
    allowed_ips = _configured_allowed_ips()
    provided_sig = str(signature or "").strip()

    if provided_sig and hmac_secret:
        if _validate_hmac_signature(body, provided_sig, hmac_secret):
            return True
        # Suno provider IPs may send non-HMAC headers; trust the IP allowlist when configured.
        if allowed_ips and client_ip and client_ip in allowed_ips:
            logger.info(
                "Suno callback accepted via IP allowlist despite invalid signature. IP=%s",
                client_ip,
            )
            return True
        logger.warning(
            "Suno callback rejected: invalid HMAC signature. IP=%s",
            client_ip,
        )
        return False

    if provided_sig and not hmac_secret:
        logger.warning(
            "Suno callback rejected: signature provided but HMAC secret is not configured. IP=%s",
            client_ip,
        )
        return False

    if allowed_ips and client_ip and client_ip in allowed_ips:
        return True

    # Suno provider webhooks do not sign payloads; accept unsigned callbacks.
    if hmac_secret and not provided_sig:
        logger.info(
            "Suno callback accepted without signature (provider does not sign). IP=%s",
            client_ip,
        )
        return True

    if settings.debug and not allowed_ips and not hmac_secret:
        logger.warning(
            "Callback accepted without HMAC or IP validation (dev mode). "
            "Configure PLATFORM_SUNO_CALLBACK_HMAC_SECRET for production."
        )
        return True

    return False


def _is_terminal_success_status(status: str | None) -> bool:
    """Return True when a stored task/song status is already SUCCESS."""
    if not status:
        return False
    return str(status).strip().upper() in {
        "SUCCESS",
        "COMPLETE",
        "COMPLETED",
        "DONE",
        "SUNO_SUCCESS",
    }


# ---------------------------------------------------------------------------
# Callback Processing Logic
# ---------------------------------------------------------------------------


def _extract_task_id_from_payload(payload: SunoCallbackPayload) -> str:
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
        task_id = payload.data.get("task_id") or payload.data.get("taskId")
        if task_id:
            return str(task_id).strip()

    return ""


def _extract_task_id_from_raw(raw_payload: dict[str, Any]) -> str:
    from platform_api.services.suno_audio_resolver import extract_callback_task_id

    return extract_callback_task_id(raw_payload)


def _extract_status_from_payload(payload: SunoCallbackPayload) -> TaskStatus | None:
    """Map callback status string to TaskStatus enum."""
    status_str = payload.status
    if payload.data and isinstance(payload.data, dict):
        status_str = status_str or payload.data.get("status")
        callback_type = str(
            payload.data.get("callbackType") or payload.data.get("callback_type") or ""
        ).lower()
        if callback_type == "complete":
            return TaskStatus.SUCCESS
        if callback_type in {"failed", "error"}:
            return TaskStatus.FAILED

    if not status_str:
        return None

    status_upper = str(status_str).upper().strip()
    if is_suno_success_status(status_upper):
        return TaskStatus.SUCCESS
    if is_suno_failure_status(status_upper):
        return TaskStatus.FAILED
    if status_upper in ("FAILED", "ERROR", "FAILURE", "CANCELLED", "CANCELED"):
        return TaskStatus.FAILED
    return None


def _extract_error_message_from_raw(raw_payload: dict[str, Any]) -> str:
    data = raw_payload.get("data")
    if isinstance(data, dict):
        for key in ("errorMessage", "error_message", "msg", "message"):
            value = str(data.get(key, "")).strip()
            if value:
                return value
    for key in ("errorMessage", "error_message", "msg", "message"):
        value = str(raw_payload.get(key, "")).strip()
        if value:
            return value
    status = ""
    if isinstance(data, dict):
        status = str(data.get("status", "")).strip()
    return suno_task_failure_message(status=status)


def _extract_status_from_raw(raw_payload: dict[str, Any]) -> TaskStatus | None:
    from platform_api.services.suno_audio_resolver import callback_indicates_success

    if callback_indicates_success(raw_payload):
        return TaskStatus.SUCCESS
    return _extract_status_from_payload(SunoCallbackPayload.model_validate(raw_payload))


def _extract_audio_urls(payload: SunoCallbackPayload) -> tuple[str | None, str | None]:
    """Extract Primary and Secondary channel track audio URLs from the callback payload.

    Returns:
        Tuple of (audio_url_ok, audio_url_alt).
    """
    audio_ok = payload.audio_url_ok
    audio_alt = payload.audio_url_alt

    # Try nested data field
    if payload.data and isinstance(payload.data, dict):
        audio_ok = audio_ok or payload.data.get("audio_url_ok") or payload.data.get("audioUrlOk")
        audio_alt = audio_alt or payload.data.get("audio_url_alt") or payload.data.get("audioUrlAlt")

        # Single audio_url might be the Primary channel track
        if not audio_ok and payload.data.get("audio_url"):
            audio_ok = payload.data["audio_url"]

        nested_clips = payload.data.get("data")
        if isinstance(nested_clips, list):
            from platform_api.clients.suno_client import _extract_clip_download_url

            clip_urls = [
                _extract_clip_download_url(item)
                for item in nested_clips
                if isinstance(item, dict)
            ]
            clip_urls = [url for url in clip_urls if url]
            if clip_urls:
                audio_ok = audio_ok or clip_urls[0]
                if len(clip_urls) > 1:
                    audio_alt = audio_alt or clip_urls[1]

    # Fallback to top-level audio_url as Primary channel track
    if not audio_ok and payload.audio_url:
        audio_ok = payload.audio_url

    return audio_ok, audio_alt


def _extract_audio_urls_from_raw(raw_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    from platform_api.services.suno_audio_resolver import extract_callback_download_urls

    parsed = extract_callback_download_urls(raw_payload)
    if parsed.audio_url_ok or parsed.audio_url_alt:
        return parsed.audio_url_ok or None, parsed.audio_url_alt or None
    payload = SunoCallbackPayload.model_validate(raw_payload)
    return _extract_audio_urls(payload)


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
    batch_service: BatchServiceDep,
    image_job_service: ImageJobServiceDep,
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
    client_ip = _resolve_callback_client_ip(request)
    callback_signature = _extract_callback_signature(request, x_signature)

    # --- HMAC / IP Validation ---
    if not _validate_callback_request(client_ip, body, callback_signature):
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
    external_task_id = _extract_task_id_from_raw(raw_payload) or _extract_task_id_from_payload(payload)
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
    new_status = _extract_status_from_raw(raw_payload) or _extract_status_from_payload(payload)
    if new_status is None:
        logger.warning(
            "Suno callback for task_id=%s: could not determine status. Ignoring.",
            external_task_id,
        )
        return Response(status_code=200, content="OK")

    # Guard: never downgrade SUCCESS → FAILED (blocks refund farming).
    current_status = task_data.get("status")
    if (
        new_status == TaskStatus.FAILED
        and _is_terminal_success_status(
            current_status.value if hasattr(current_status, "value") else current_status
        )
    ):
        logger.warning(
            "Suno callback ignored SUCCESS→FAILED downgrade for task_id=%s "
            "(current=%s). Refund path will not run.",
            external_task_id,
            current_status,
        )
        return Response(status_code=200, content="OK")

    audio_url_ok, audio_url_alt = _extract_audio_urls_from_raw(raw_payload)
    if not audio_url_ok and not audio_url_alt:
        audio_url_ok, audio_url_alt = _extract_audio_urls(payload)

    from platform_api.services.suno_audio_resolver import normalize_http_download_url

    audio_url_ok = normalize_http_download_url(audio_url_ok) or None
    audio_url_alt = normalize_http_download_url(audio_url_alt) or None

    if new_status == TaskStatus.SUCCESS and not audio_url_ok and not audio_url_alt:
        try:
            from platform_api.dependencies import get_db_pool
            from platform_api.services.suno_audio_resolver import (
                poll_suno_generate_with_pool,
                urls_from_generate_poll,
            )

            poll_result = await poll_suno_generate_with_pool(get_db_pool(), external_task_id)
            if poll_result.state == "success":
                refreshed = urls_from_generate_poll(poll_result)
                audio_url_ok = normalize_http_download_url(refreshed.audio_url_ok) or None
                audio_url_alt = normalize_http_download_url(refreshed.audio_url_alt) or None
        except Exception as exc:
            logger.warning(
                "Suno callback record-info refresh failed for task_id=%s: %s",
                external_task_id,
                str(exc)[:200],
            )

    persist_status = new_status
    task_error_message: str | None = None
    if new_status == TaskStatus.SUCCESS and not audio_url_ok and not audio_url_alt:
        logger.warning(
            "Suno callback success without download URLs for task_id=%s; "
            "keeping pending for reconcile.",
            external_task_id,
        )
        persist_status = TaskStatus.PENDING

    if persist_status == TaskStatus.FAILED:
        task_error_message = _extract_error_message_from_raw(raw_payload)
        try:
            from platform_api.dependencies import get_db_pool
            from platform_api.services.suno_audio_resolver import poll_suno_generate_with_pool

            poll_result = await poll_suno_generate_with_pool(get_db_pool(), external_task_id)
            if poll_result.state == "failed" and poll_result.error:
                task_error_message = poll_result.error
        except Exception as exc:
            logger.warning(
                "Suno callback record-info refresh failed for task_id=%s: %s",
                external_task_id,
                str(exc)[:200],
            )

    # --- Update Task Record (Req 11.3, 11.6) ---
    task_id = UUID(str(task_data["id"]))
    user_id = str(task_data["user_id"])

    await task_repo.update_status(
        task_id,
        status=persist_status,
        audio_url_ok=audio_url_ok,
        audio_url_alt=audio_url_alt,
        error_message=task_error_message,
    )

    if persist_status == TaskStatus.SUCCESS and (audio_url_ok or audio_url_alt):
        try:
            from platform_api.dependencies import get_db_pool
            from platform_api.services.streaming_upload_service import StreamingUploadService

            StreamingUploadService(get_db_pool()).schedule_suno_streaming_upload(suno_task_id=task_id)
        except Exception as exc:
            logger.warning("Failed to schedule streaming upload for task %s: %s", task_id, exc)

    song_id_value = task_data.get("song_id")
    batch_id_value = task_data.get("batch_id")
    auto_run_images = False
    parsed_batch_id: UUID | None = None
    if batch_id_value:
        parsed_batch_id = UUID(str(batch_id_value))
        try:
            batch = await batch_service.get_batch_for_user(
                batch_id=parsed_batch_id,
                user_id=UUID(user_id),
            )
            auto_run_images = bool(batch and getattr(batch, "auto_gen_image", False))
        except Exception:
            auto_run_images = False

    if song_id_value and batch_id_value and persist_status != TaskStatus.PENDING:
        try:
            await batch_service.handle_suno_task_update(
                song_id=UUID(str(song_id_value)),
                batch_id=UUID(str(batch_id_value)),
                status=persist_status,
                error_message=task_error_message,
            )
        except Exception as exc:
            logger.error(
                "Batch callback handoff failed for task_id=%s: %s",
                task_id,
                str(exc)[:200],
            )

    if auto_run_images and parsed_batch_id is not None and persist_status == TaskStatus.SUCCESS:
        asyncio.create_task(
            run_image_jobs_until_empty(
                image_job_service,
                user_id=user_id,
                batch_id=str(parsed_batch_id),
            )
        )

    logger.info(
        "Suno callback processed: task_id=%s, external_id=%s, status=%s",
        task_id,
        external_task_id,
        persist_status.value,
    )

    # --- Push WebSocket Notification (Req 11.3) ---
    notification_payload = {
        "task_id": str(task_id),
        "external_task_id": external_task_id,
        "status": persist_status.value,
    }
    if persist_status == TaskStatus.SUCCESS:
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
