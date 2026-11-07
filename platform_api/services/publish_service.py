"""Post for Me publishing service: accounts, upload jobs, charges, results."""

from __future__ import annotations

import asyncio
import hmac
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    NotFoundError,
    ValidationError,
)
from platform_api.repositories.publish_repo import (
    PublishAccountRecord,
    PublishConnectSessionRecord,
    PublishJobRecord,
    PublishRepository,
)
from platform_api.services.credit_units import units_to_credits
from platform_api.services.publish_pricing import POSTFORME_PUBLISH_OP

logger = logging.getLogger(__name__)

PUBLISH_PLATFORM = "youtube"
SUPPORTED_PLATFORMS = ("youtube",)
EXTERNAL_ID_PREFIX = "camxora"
UPLOAD_URL_TTL = timedelta(hours=6)
CONNECT_SESSION_TTL = timedelta(minutes=30)

# Hosted originals: uploaded, fetched by the provider, then safe to delete once
# the signed URL they came with has expired.
PUBLISH_MEDIA_PREFIX = "publish/"
MEDIA_RETENTION_DAYS = 7
MEDIA_PURGE_INTERVAL_SECONDS = 6 * 3600
_last_media_purge = 0.0
_media_purge_lock = asyncio.Lock()

STATUS_PENDING_UPLOAD = "pending_upload"
STATUS_PENDING_PAYMENT = "pending_payment"
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PublishCallbackResult:
    title: str
    message: str
    status: str


@dataclass(frozen=True, slots=True)
class PublishConnectionStart:
    session_id: str
    auth_url: str
    status: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError("publish_at must be an ISO 8601 timestamp.") from exc
    return _as_utc(parsed)


def _parse_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw = [str(part).strip() for part in value]
    else:
        raw = []
    return [part for part in raw if part][:50]


def _external_id(user_id: str, profile_id: str) -> str:
    return f"{EXTERNAL_ID_PREFIX}:{user_id}:{profile_id}"


def _parse_external_id(value: str | None) -> tuple[str, str] | None:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 3 or parts[0] != EXTERNAL_ID_PREFIX:
        return None
    try:
        user_id = str(UUID(parts[1]))
        profile_id = str(UUID(parts[2]))
    except ValueError:
        return None
    return (user_id, profile_id)


class PublishService:
    def __init__(
        self,
        *,
        db: Any,
        repo: PublishRepository,
        client: Any,
        billing: Any,
        enabled: bool = False,
        webhook_secret: str = "",
    ) -> None:
        self._db = db
        self._repo = repo
        self._client = client
        self._billing = billing
        self._enabled = bool(enabled)
        self._webhook_secret = str(webhook_secret or "")

    # --- Hosted media retention --------------------------------------------

    async def _purge_stale_media(self) -> None:
        """Delete hosted originals older than the media-URL lifetime.

        Every publish pushes the original (often several GB) to B2 and the
        provider fetches it within minutes; the object then stayed forever.
        This mirrors the bucket lifecycle rule we would otherwise need, so it
        works without dashboard access. Runs at most every few hours, from the
        listing the desktop already polls.
        """
        global _last_media_purge
        now = time.time()
        if now - _last_media_purge < MEDIA_PURGE_INTERVAL_SECONDS:
            return
        async with _media_purge_lock:
            if time.time() - _last_media_purge < MEDIA_PURGE_INTERVAL_SECONDS:
                return
            _last_media_purge = time.time()
            try:
                from platform_api.services.storage_service import StorageService
                from platform_api.services.streaming_config_service import (
                    resolve_streaming_storage_config,
                )

                config = await resolve_streaming_storage_config(self._db)
                if not config.configured:
                    return
                storage = StorageService.from_config(config)
                objects = await storage.list_objects(PUBLISH_MEDIA_PREFIX)
            except Exception:
                logger.warning("Publish media listing failed; cleanup skipped.", exc_info=True)
                return
            cutoff = datetime.now(timezone.utc) - timedelta(days=MEDIA_RETENTION_DAYS)
            removed = 0
            for item in objects:
                modified = item.get("last_modified")
                if not isinstance(modified, datetime) or modified >= cutoff:
                    continue
                key = str(item.get("key") or "")
                if not key:
                    continue
                try:
                    await storage.delete_object(key)
                    removed += 1
                except Exception:
                    logger.warning("Could not delete publish media %s", key, exc_info=True)
            if removed:
                logger.info(
                    "Deleted %s publish media object(s) older than %s days.",
                    removed,
                    MEDIA_RETENTION_DAYS,
                )

    # --- Feature flag -------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def require_enabled(self) -> None:
        if not self._enabled:
            raise ValidationError(
                "Post for Me publishing is disabled.",
                details={"error_code": "PUBLISH_DISABLED"},
            )

    def verify_webhook_secret(self, value: str | None) -> bool:
        """Fail closed: an unset secret rejects every webhook."""
        expected = str(self._webhook_secret or "")
        if not expected:
            return False
        return hmac.compare_digest(str(value or ""), expected)

    # --- Accounts -----------------------------------------------------------

    async def list_accounts(
        self, user_id: str, *, profile_id: str | None = None
    ) -> list[PublishAccountRecord]:
        self.require_enabled()
        return await self._repo.list_accounts(user_id, profile_id=profile_id)

    async def start_connection(
        self,
        *,
        user_id: str,
        profile_id: str,
        platform: str,
        callback_url: str | None = None,
    ) -> PublishConnectionStart:
        self.require_enabled()
        normalized_platform = str(platform or "").strip().lower() or PUBLISH_PLATFORM
        if normalized_platform not in SUPPORTED_PLATFORMS:
            raise ValidationError(
                f"Unsupported publishing platform: {normalized_platform}",
                details={"platform": normalized_platform},
            )
        await self._ensure_profile_owned(user_id, profile_id)

        auth = await self._client.create_account_auth_url(
            platform=normalized_platform,
            external_id=_external_id(user_id, profile_id),
            redirect_url_override=callback_url,
        )
        session = await self._repo.create_connect_session(
            user_id=user_id,
            profile_id=profile_id,
            platform=normalized_platform,
            expires_at=_utcnow() + CONNECT_SESSION_TTL,
        )
        return PublishConnectionStart(
            session_id=session.id,
            auth_url=str(auth.get("url") or ""),
            status="pending_browser",
        )

    async def finalize_connection(self, params: dict[str, Any]) -> PublishCallbackResult:
        """Handle the Post for Me OAuth redirect.

        Post for Me does not echo a custom state, so ownership is recovered from
        the ``external_id`` we set on the auth URL (``camxora:user:profile``).
        """
        success = str(params.get("isSuccess") or "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        error_message = str(params.get("error") or "").strip()
        raw_account_ids = params.get("accountIds") or []
        if isinstance(raw_account_ids, str):
            account_ids = [part.strip() for part in raw_account_ids.split(",") if part.strip()]
        elif isinstance(raw_account_ids, list):
            account_ids = [str(item).strip() for item in raw_account_ids if str(item).strip()]
        else:
            account_ids = []

        if not success:
            return PublishCallbackResult(
                title="YouTube connection failed",
                message=error_message or "The connection was cancelled or rejected.",
                status="failed",
            )
        if not account_ids:
            return PublishCallbackResult(
                title="YouTube connection failed",
                message="Post for Me did not return a connected account.",
                status="failed",
            )

        accounts = await self._client.list_accounts(account_ids=account_ids)
        linked = 0
        rejected = 0
        last_user_id: str | None = None
        last_profile_id: str | None = None
        pending_sessions = await self._repo.list_pending_connect_sessions(PUBLISH_PLATFORM)
        fallback_session = pending_sessions[0] if len(pending_sessions) == 1 else None
        for account in accounts:
            parsed = _parse_external_id(str(account.get("external_id") or ""))
            if parsed is None and fallback_session is not None:
                parsed = (fallback_session.user_id, fallback_session.profile_id)
            if parsed is None:
                rejected += 1
                continue
            account_user_id, account_profile_id = parsed
            last_user_id = account_user_id
            last_profile_id = account_profile_id
            await self._repo.upsert_account(
                user_id=account_user_id,
                profile_id=account_profile_id,
                platform=str(account.get("platform") or PUBLISH_PLATFORM),
                postforme_account_id=str(account.get("id") or ""),
                external_id=str(account.get("external_id") or ""),
                username=account.get("username"),
                display_name=_display_name(account),
                avatar_url=account.get("profile_photo_url"),
                metadata=_account_metadata(account),
            )
            linked += 1

        if last_user_id and last_profile_id:
            session = await self._repo.latest_connect_session(last_user_id, last_profile_id)
            if session is not None:
                await self._repo.finish_connect_session(
                    session.id,
                    status="connected" if linked else "failed",
                    account_ids=account_ids,
                    error_message=None if linked else "No account matched this CAMXORA profile.",
                )

        if linked:
            return PublishCallbackResult(
                title="YouTube connected",
                message=(
                    f"{linked} account{'s' if linked != 1 else ''} connected. "
                    "You can return to CAMXORA."
                ),
                status="connected",
            )
        return PublishCallbackResult(
            title="YouTube connection failed",
            message=(
                "No account could be linked to this CAMXORA profile."
                + (f" {rejected} account(s) did not match." if rejected else "")
            ),
            status="failed",
        )

    async def disconnect_account(self, user_id: str, account_id: str) -> None:
        self.require_enabled()
        account = await self._repo.get_account(user_id, account_id)
        if account is None:
            raise NotFoundError("Publishing account not found.")
        try:
            await self._client.disconnect_account(account.postforme_account_id)
        except ExternalServiceError as exc:
            logger.warning("Post for Me disconnect failed for %s: %s", account_id, exc)
        if not await self._repo.disconnect_account(user_id, account_id):
            raise NotFoundError("Publishing account not found.")

    async def latest_connect_session(
        self, user_id: str, profile_id: str
    ) -> PublishConnectSessionRecord | None:
        return await self._repo.latest_connect_session(user_id, profile_id)

    async def sync_accounts(
        self, *, user_id: str, profile_id: str, platform: str = PUBLISH_PLATFORM
    ) -> list[PublishAccountRecord]:
        """Link accounts already connected in Post for Me to this profile.

        This makes Connect idempotent: if the provider already has the account,
        we do not start a duplicate OAuth flow.
        """
        self.require_enabled()
        normalized_platform = str(platform or "").strip().lower() or PUBLISH_PLATFORM
        if normalized_platform not in SUPPORTED_PLATFORMS:
            raise ValidationError(
                f"Unsupported publishing platform: {normalized_platform}",
                details={"platform": normalized_platform},
            )
        await self._ensure_profile_owned(user_id, profile_id)
        external_id = _external_id(user_id, profile_id)
        accounts = await self._client.list_accounts(
            external_id=external_id, platform=normalized_platform
        )
        linked: list[PublishAccountRecord] = []
        for account in accounts:
            if str(account.get("platform") or "").strip().lower() != normalized_platform:
                continue
            linked.append(
                await self._repo.upsert_account(
                    user_id=user_id,
                    profile_id=profile_id,
                    platform=normalized_platform,
                    postforme_account_id=str(account.get("id") or ""),
                    external_id=str(account.get("external_id") or external_id),
                    username=account.get("username"),
                    display_name=_display_name(account),
                    avatar_url=account.get("profile_photo_url"),
                    metadata=_account_metadata(account),
                )
            )
        return linked

    # --- Quote --------------------------------------------------------------

    async def quote(self, user_id: str) -> dict[str, Any]:
        self.require_enabled()
        quote = await self._billing.quote(op=POSTFORME_PUBLISH_OP, user_id=UUID(user_id))
        wallet = await self._billing.wallet_view(UUID(user_id))
        balance_units = int(wallet.get("balance_units") or 0)
        return {
            "op": quote.op,
            "credits_per_upload": quote.amount_credits,
            "amount_units": quote.amount_units,
            "balance": units_to_credits(balance_units),
            "available": balance_units >= quote.amount_units,
            "platforms": list(SUPPORTED_PLATFORMS),
        }

    # --- Jobs ---------------------------------------------------------------

    async def create_job(
        self,
        *,
        user_id: str,
        profile_id: str,
        platform: str,
        batch_id: str | None,
        role: str,
        title: str,
        description: str | None,
        tags: Any,
        privacy_status: str,
        publish_at: str | None,
        made_for_kids: bool,
        contains_synthetic_media: bool,
        file_name: str,
        file_size_bytes: int | None,
        file_checksum: str | None,
        file_path: str | None,
        thumbnail_path: str | None,
        media_url: str | None = None,
    ) -> dict[str, Any]:
        self.require_enabled()
        normalized_platform = str(platform or "").strip().lower() or PUBLISH_PLATFORM
        if normalized_platform not in SUPPORTED_PLATFORMS:
            raise ValidationError(
                f"Unsupported publishing platform: {normalized_platform}",
                details={"platform": normalized_platform},
            )
        normalized_title = str(title or "").strip()
        if not normalized_title:
            raise ValidationError("A video title is required.")
        if len(normalized_title) > 100:
            raise ValidationError("YouTube titles are limited to 100 characters.")

        profile = await self._ensure_profile_owned(user_id, profile_id)
        if batch_id:
            await self._ensure_batch_owned(user_id, batch_id)

        normalized_role = str(role or "OK").strip().upper() or "OK"
        if batch_id:
            # One publish per batch/channel/role. A repeated click (or a retried
            # upload) must not open a second transfer, charge twice, or create a
            # second YouTube post.
            existing = await self._repo.latest_job_for_slot(
                user_id=user_id,
                batch_id=batch_id,
                profile_id=profile_id,
                role=normalized_role,
            )
            reused = await self._reuse_or_retire_job(
                existing, size_bytes=file_size_bytes
            )
            if reused is not None:
                logger.info(
                    "Publish job reused instead of creating another: batch=%s role=%s status=%s",
                    batch_id,
                    normalized_role,
                    reused.get("status"),
                )
                reused["credits_per_upload"] = await self._quote_credits(user_id)
                reused["platforms"] = [normalized_platform]
                return reused

        account = await self._account_for_profile(user_id, profile_id, normalized_platform)
        if account is None:
            raise ValidationError(
                "Connect a YouTube channel before publishing.",
                details={"error_code": "PUBLISH_ACCOUNT_MISSING"},
            )
        visibility = _normalize_visibility(privacy_status, profile.get("youtube_config"))
        profile_youtube_config = (
            profile.get("youtube_config")
            if isinstance(profile.get("youtube_config"), dict)
            else {}
        )
        scheduled_at = None
        if visibility == "scheduled":
            scheduled_at = await self._resolve_scheduled_at(publish_at, batch_id)
            if scheduled_at is None:
                raise ValidationError("publish_at is required when visibility is scheduled.")
            if scheduled_at <= _utcnow():
                raise ValidationError("publish_at must be in the future.")

        external_media_url = str(media_url or "").strip()
        if external_media_url:
            # Media already uploaded by us (B2): the provider fetches the URL,
            # so there is no presigned upload leg and no size wall.
            media = {"media_url": external_media_url, "upload_url": None}
        else:
            media = await self._client.create_media_upload_url()
        thumbnail_media_url = None
        thumbnail_upload_url = None
        if not external_media_url and str(thumbnail_path or "").strip():
            thumbnail_media = await self._client.create_media_upload_url()
            thumbnail_media_url = thumbnail_media["media_url"]
            thumbnail_upload_url = thumbnail_media["upload_url"]

        job_uid = str(uuid4())
        expires_at = _utcnow() + UPLOAD_URL_TTL
        job = await self._repo.create_job(
            user_id=user_id,
            job_uid=job_uid,
            batch_id=batch_id,
            profile_id=profile_id,
            role=str(role or "OK").strip().upper() or "OK",
            title=normalized_title,
            description=str(description or "").strip() or None,
            tags=_parse_tags(tags),
            privacy_status="private" if visibility == "scheduled" else visibility,
            social_account_id=account.postforme_account_id,
            platform=normalized_platform,
            media_url=media["media_url"],
            upload_url=media["upload_url"],
            upload_expires_at=expires_at,
            file_path=str(file_path or "").strip() or None,
            file_size_bytes=file_size_bytes,
            file_checksum=str(file_checksum or "").strip() or None,
            thumbnail_path=str(thumbnail_path or "").strip() or None,
            thumbnail_media_url=thumbnail_media_url,
            profile_config={
                "category": profile_youtube_config.get("category"),
                "made_for_kids": bool(made_for_kids),
                "contains_synthetic_media": bool(contains_synthetic_media),
                "visibility": visibility,
            },
            scheduled_at=scheduled_at,
        )
        if external_media_url:
            # The media is already hosted: there is nothing for the client to
            # upload, so finish the job server-side (charge + hand the URL to the
            # provider). Leaving it pending_upload stranded every URL-based
            # publish in production.
            completed = await self.complete_job(user_id=user_id, job_uid=job.job_uid)
            return {
                "job_uid": completed.get("job_uid", job.job_uid),
                "status": completed.get("status", job.status),
                "upload_url": None,
                "upload_expires_at": None,
                "media_url": job.media_url,
                "thumbnail_upload_url": None,
                "thumbnail_media_url": thumbnail_media_url,
                "file_name": str(file_name or "").strip(),
                "credits_per_upload": (await self._quote_credits(user_id)),
                "platforms": [normalized_platform],
                "existing": False,
            }
        return {
            "job_uid": job.job_uid,
            "status": job.status,
            "upload_url": job.upload_url,
            "upload_expires_at": job.upload_expires_at.isoformat() if job.upload_expires_at else None,
            "media_url": job.media_url,
            "thumbnail_upload_url": thumbnail_upload_url,
            "thumbnail_media_url": thumbnail_media_url,
            "file_name": str(file_name or "").strip(),
            "credits_per_upload": (await self._quote_credits(user_id)),
            "platforms": [normalized_platform],
            "existing": False,
        }

    async def _reuse_or_retire_job(
        self,
        job: Any,
        *,
        size_bytes: int | None,
    ) -> dict[str, Any] | None:
        """Existing-job view when a repeat click must not start another upload.

        Returns None when a fresh job is allowed. A stale ``pending_upload`` job
        whose media was already hosted (older clients never finalised those) is
        retired first so Progress stops reporting it as "Uploading" forever.
        """
        if job is None:
            return None
        status = str(job.status)
        different_file = (
            size_bytes is not None
            and job.file_size_bytes is not None
            and int(job.file_size_bytes) != int(size_bytes)
        )
        if status in {STATUS_QUEUED, STATUS_PROCESSING} and not different_file:
            # A provider job that never produced a video and has not moved for
            # hours was abandoned (webhook lost, provider outage). Treating it as
            # "already uploading" blocked every retry of that video forever.
            stamp = job.updated_at or job.created_at
            if stamp is not None and _as_utc(stamp) < _utcnow() - timedelta(minutes=45):
                # A charged job that never produced a video must give the
                # credits back automatically - the customer got nothing.
                await self._refund_job(
                    job,
                    error_code="UPLOAD_STALLED",
                    error_message="The publishing provider never confirmed this upload.",
                )
                return None
            return self._existing_job_view(job, existing=True)
        if status == STATUS_SUCCESS and not different_file:
            return self._existing_job_view(job, existing=True)
        if status == STATUS_PENDING_UPLOAD and job.media_url and not different_file:
            await self._repo.set_job_status(
                job.id,
                status=STATUS_FAILED,
                error_code="UPLOAD_SUPERSEDED",
                error_message="Superseded by a new upload of the same video.",
            )
        return None

    @staticmethod
    def _existing_job_view(job: Any, *, existing: bool) -> dict[str, Any]:
        return {
            "job_uid": job.job_uid,
            "status": job.status,
            "upload_url": None,
            "upload_expires_at": None,
            "media_url": job.media_url,
            "thumbnail_upload_url": None,
            "thumbnail_media_url": job.thumbnail_media_url,
            "file_name": str(job.title or ""),
            "credits_per_upload": 0,
            "platforms": [str(getattr(job, "platform", "") or PUBLISH_PLATFORM)],
            "existing": bool(existing),
        }

    async def complete_job(
        self,
        *,
        user_id: str,
        job_uid: str,
        checksum: str | None = None,
    ) -> dict[str, Any]:
        self.require_enabled()
        job = await self._repo.get_job(user_id, job_uid)
        if job is None:
            raise NotFoundError("Publish job not found.")
        if job.status == STATUS_SUCCESS:
            return _job_view(job)
        if str(job.status) in {"processing", "queued", "uploading"}:
            # Media was supplied by URL and the job was finalised server-side;
            # a client that still calls complete must not fail (or double-post).
            return _job_view(job)
        if job.status in {STATUS_FAILED, STATUS_CANCELLED}:
            raise ValidationError("This publish job has already finished.", details={"status": job.status})
        if job.status not in {STATUS_PENDING_UPLOAD, STATUS_PENDING_PAYMENT}:
            raise ValidationError(
                "This publish job is not waiting for an upload.",
                details={"status": job.status},
            )
        if job.upload_expires_at and _as_utc(job.upload_expires_at) <= _utcnow():
            await self._repo.set_job_status(
                job.id,
                status=STATUS_FAILED,
                error_code="UPLOAD_URL_EXPIRED",
                error_message="The upload link expired before the file finished uploading.",
            )
            raise ValidationError("The upload link expired. Start the upload again.")
        if checksum and job.file_checksum and str(checksum) != job.file_checksum:
            raise ValidationError("Uploaded file checksum does not match the job.")

        charged_now = False
        if job.credits_charged_units <= 0:
            ref_id = self._charge_ref(job)
            try:
                charge = await self._billing.charge(
                    user_id=UUID(user_id),
                    op=POSTFORME_PUBLISH_OP,
                    ref_id=ref_id,
                    product="desktop",
                )
            except InsufficientCreditsError:
                await self._repo.set_job_status(
                    job.id,
                    status=STATUS_PENDING_PAYMENT,
                    error_code="INSUFFICIENT_CREDITS",
                    error_message="Top up credits to publish this upload.",
                )
                raise
            charged_now = True
            await self._repo.mark_job_charged(
                job.id,
                credits_charged_units=int(charge.get("amount_units") or 0),
                credit_ref_id=ref_id,
                status=STATUS_QUEUED,
            )
            job = await self._repo.get_job(user_id, job_uid) or job

        payload = self._build_post_payload(job)
        try:
            post = await self._client.create_social_post(payload)
        except Exception as exc:
            await self._refund_job(
                job,
                error_code=_error_code(exc, "POST_CREATE_FAILED"),
                error_message=_error_message(exc, "The publishing service could not create the post."),
            )
            raise
        post_id = str(post.get("id") or "").strip()
        if not post_id:
            await self._refund_job(
                job,
                error_code="POST_CREATE_FAILED",
                error_message="The publishing service did not return a post id.",
            )
            raise ExternalServiceError("The publishing service did not return a post id.")
        await self._repo.mark_job_posted(
            job.id,
            postforme_post_id=post_id,
            status=STATUS_PROCESSING,
            attempt_count=max(0, job.attempt_count),
        )
        refreshed = await self._repo.get_job(user_id, job_uid) or job
        logger.info(
            "Publish job queued: job_uid=%s post_id=%s charged=%s",
            job_uid,
            post_id,
            charged_now,
        )
        return _job_view(refreshed)

    async def sync_post_results(self, postforme_post_id: str) -> dict[str, Any] | None:
        job = await self._repo.get_job_by_post_id(postforme_post_id)
        if job is None:
            return None
        results = await self._client.list_social_post_results(postforme_post_id)
        first_success: dict[str, Any] | None = None
        first_failure_message = ""
        for item in results:
            platform_data = item.get("platform_data") if isinstance(item.get("platform_data"), dict) else {}
            success = bool(item.get("success"))
            if success and first_success is None:
                first_success = item
            if not success and not first_failure_message:
                first_failure_message = str(item.get("error") or "").strip()
            await self._repo.upsert_result(
                job_id=job.id,
                platform=str(item.get("platform") or job.platform),
                social_account_id=str(item.get("social_account_id") or job.social_account_id or ""),
                postforme_result_id=str(item.get("id") or "").strip() or None,
                success=success,
                platform_post_id=str(platform_data.get("id") or "").strip() or None,
                platform_url=str(platform_data.get("url") or "").strip() or None,
                error_message=None if success else str(item.get("error") or "").strip() or None,
                details=item,
            )

        total, succeeded = await self._repo.count_results(job.id)
        if total <= 0:
            return _job_view(job)
        if succeeded > 0:
            platform_data = first_success.get("platform_data") if first_success else {}
            platform_data = platform_data if isinstance(platform_data, dict) else {}
            await self._repo.mark_job_success(
                job.id,
                platform_post_id=str(platform_data.get("id") or "").strip() or None,
                platform_url=str(platform_data.get("url") or "").strip() or None,
                result_payload={"results": results},
            )
        else:
            await self._refund_job(
                job,
                error_code="POST_RESULT_FAILED",
                error_message=first_failure_message or "The platform rejected the upload.",
            )
        refreshed = await self._repo.get_job(job.user_id, job.job_uid) or job
        return _job_view(refreshed)

    async def sync_processing_jobs(self, *, older_than_seconds: int = 600) -> int:
        jobs = await self._repo.list_processing_jobs(older_than_seconds=older_than_seconds)
        synced = 0
        for job in jobs:
            if not job.postforme_post_id:
                continue
            try:
                await self.sync_post_results(job.postforme_post_id)
                synced += 1
            except Exception:
                logger.exception("Failed to sync publish job %s", job.job_uid)
        return synced

    async def get_job(self, user_id: str, job_uid: str) -> dict[str, Any]:
        self.require_enabled()
        job = await self._repo.get_job(user_id, job_uid)
        if job is None:
            raise NotFoundError("Publish job not found.")
        return _job_view(job)

    async def list_jobs(
        self,
        user_id: str,
        *,
        batch_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.require_enabled()
        try:
            expired = await self._repo.expire_pending_uploads()
            if expired:
                logger.info("Marked %s publish job(s) failed after upload-URL expiry.", expired)
        except Exception:
            logger.warning("Publish upload expiry sweep failed.", exc_info=True)
        try:
            await self._purge_stale_media()
        except Exception:
            logger.warning("Publish media cleanup failed.", exc_info=True)
        jobs = await self._repo.list_jobs(
            user_id, batch_id=batch_id, status=status, limit=limit
        )
        return [_job_view(job) for job in jobs]

    async def retry_job(self, *, user_id: str, job_uid: str) -> dict[str, Any]:
        self.require_enabled()
        job = await self._repo.get_job(user_id, job_uid)
        if job is None:
            raise NotFoundError("Publish job not found.")
        if job.status not in {STATUS_FAILED, STATUS_CANCELLED, STATUS_PENDING_PAYMENT}:
            raise ValidationError(
                "Only failed, cancelled, or unpaid jobs can be retried.",
                details={"status": job.status},
            )
        media = await self._client.create_media_upload_url()
        await self._repo.reset_job_for_retry(
            job.id,
            media_url=media["media_url"],
            upload_url=media["upload_url"],
            upload_expires_at=_utcnow() + UPLOAD_URL_TTL,
        )
        refreshed = await self._repo.get_job(user_id, job_uid) or job
        return {
            **_job_view(refreshed),
            "upload_url": refreshed.upload_url,
            "media_url": refreshed.media_url,
        }

    async def cancel_job(self, *, user_id: str, job_uid: str) -> dict[str, Any]:
        self.require_enabled()
        job = await self._repo.get_job(user_id, job_uid)
        if job is None:
            raise NotFoundError("Publish job not found.")
        if job.status == STATUS_SUCCESS:
            raise ValidationError("A published upload cannot be cancelled.")
        if job.credits_charged_units > 0:
            await self._refund_job(
                job,
                error_code="CANCELLED",
                error_message="Cancelled by the user.",
                status=STATUS_CANCELLED,
            )
        else:
            await self._repo.set_job_status(
                job.id,
                status=STATUS_CANCELLED,
                error_code="CANCELLED",
                error_message="Cancelled by the user.",
            )
        refreshed = await self._repo.get_job(user_id, job_uid) or job
        return _job_view(refreshed)

    # --- Helpers ------------------------------------------------------------

    async def _quote_credits(self, user_id: str) -> float:
        quote = await self._billing.quote(op=POSTFORME_PUBLISH_OP, user_id=UUID(user_id))
        return float(quote.amount_credits)

    def _charge_ref(self, job: PublishJobRecord) -> str:
        if job.attempt_count <= 0:
            return job.job_uid
        return f"{job.job_uid}:r{job.attempt_count}"

    async def _refund_job(
        self,
        job: PublishJobRecord,
        *,
        error_code: str,
        error_message: str,
        status: str = STATUS_FAILED,
    ) -> None:
        refunded_units = 0
        if job.credits_charged_units > 0:
            try:
                await self._billing.refund(
                    user_id=UUID(job.user_id),
                    op=POSTFORME_PUBLISH_OP,
                    amount_credits=units_to_credits(job.credits_charged_units),
                    ref_id=job.credit_ref_id or job.job_uid,
                    product="desktop",
                )
                refunded_units = job.credits_charged_units
            except Exception:
                logger.exception("Failed to refund publish job %s", job.job_uid)
        await self._repo.set_job_status(
            job.id,
            status=status,
            error_code=error_code,
            error_message=error_message[:500],
        )
        if refunded_units:
            await self._repo.mark_job_refunded(
                job.id,
                credits_charged_units=0,
                error_code=error_code,
                error_message=error_message[:500],
                status=status,
            )

    async def _resolve_scheduled_at(
        self, value: str | None, batch_id: str | None
    ) -> datetime | None:
        """Accept ISO timestamps or the desktop's ``HH:MM`` publication time."""
        text = str(value or "").strip()
        if not text:
            return None
        clock = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if not clock:
            return _parse_iso_datetime(text)
        hour = max(0, min(23, int(clock.group(1))))
        minute = max(0, min(59, int(clock.group(2))))
        base_date = _utcnow().date()
        if batch_id:
            row = await self._db.fetchrow(
                """
                SELECT planned_from_date
                FROM batches
                WHERE id = $1::uuid
                """,
                batch_id,
            )
            planned = row.get("planned_from_date") if row else None
            if isinstance(planned, datetime):
                base_date = planned.date()
            elif isinstance(planned, date):
                base_date = planned
        candidate = datetime(
            base_date.year,
            base_date.month,
            base_date.day,
            hour,
            minute,
            tzinfo=timezone.utc,
        )
        now = _utcnow()
        while candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    async def _ensure_profile_owned(self, user_id: str, profile_id: str) -> dict[str, Any]:
        row = await self._db.fetchrow(
            """
            SELECT id, name, youtube_config
            FROM channel_profiles
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            profile_id,
            user_id,
        )
        if row is None:
            raise NotFoundError("Channel profile not found.")
        return dict(row)

    async def _ensure_batch_owned(self, user_id: str, batch_id: str) -> None:
        row = await self._db.fetchrow(
            """
            SELECT id FROM batches
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            batch_id,
            user_id,
        )
        if row is None:
            raise NotFoundError("Batch not found.")

    async def _account_for_profile(
        self, user_id: str, profile_id: str, platform: str
    ) -> PublishAccountRecord | None:
        accounts = [
            account
            for account in await self._repo.list_accounts(user_id, profile_id=profile_id)
            if account.platform == platform
        ]
        if len(accounts) > 1:
            raise ValidationError(
                "Multiple channels are linked to this profile. "
                "Disconnect the extra channels before publishing.",
                details={"error_code": "PUBLISH_ACCOUNT_AMBIGUOUS"},
            )
        return accounts[0] if accounts else None

    def _build_post_payload(self, job: PublishJobRecord) -> dict[str, Any]:
        profile_config = job.profile_config if isinstance(job.profile_config, dict) else {}
        configuration: dict[str, Any] = {
            "title": job.title,
            "privacy_status": job.privacy_status,
            "made_for_kids": bool(profile_config.get("made_for_kids", False)),
            "contains_synthetic_media": bool(
                profile_config.get("contains_synthetic_media", True)
            ),
            "tags": [part for part in str(job.tags or "").split(",") if part],
            "embeddable": True,
            "license": "youtube",
            "public_stats_viewable": True,
        }
        if profile_config.get("category"):
            configuration["category_id"] = str(profile_config["category"])
        if job.scheduled_at is not None:
            configuration["publish_at"] = _as_utc(job.scheduled_at).isoformat().replace("+00:00", "Z")

        media: dict[str, Any] = {
            "url": job.media_url,
            "skip_processing": True,
        }
        if job.thumbnail_media_url:
            media["thumbnail_url"] = job.thumbnail_media_url

        return {
            "caption": job.description or job.title,
            "external_id": job.job_uid,
            "media": [media],
            "social_accounts": [job.social_account_id],
            "account_configurations": [
                {
                    "social_account_id": job.social_account_id,
                    "configuration": configuration,
                }
            ],
        }


def _normalize_visibility(value: Any, youtube_config: Any) -> str:
    visibility = str(value or "").strip().lower()
    if not visibility and isinstance(youtube_config, dict):
        visibility = str(youtube_config.get("visibility") or "").strip().lower()
    if visibility in {"public", "unlisted", "private"}:
        return visibility
    if visibility in {"scheduled", "schedule"}:
        return "scheduled"
    return "private"


def _display_name(account: dict[str, Any]) -> str | None:
    metadata = account.get("metadata")
    if isinstance(metadata, dict) and metadata.get("display_name"):
        return str(metadata["display_name"])
    username = str(account.get("username") or "").strip()
    return username or None


def _account_metadata(account: dict[str, Any]) -> dict[str, Any]:
    metadata = account.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _job_view(job: PublishJobRecord) -> dict[str, Any]:
    return {
        "job_uid": job.job_uid,
        "status": job.status,
        "platform": job.platform,
        "provider": job.provider,
        "batch_id": job.batch_id,
        "profile_id": job.profile_id,
        "role": job.role,
        "title": job.title,
        "description": job.description,
        "privacy_status": job.privacy_status,
        "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
        "youtube_video_id": job.youtube_video_id,
        "youtube_url": job.youtube_url,
        "postforme_post_id": job.postforme_post_id,
        "credits_charged": units_to_credits(job.credits_charged_units),
        "error_code": job.error_code,
        "error_message": job.error_message,
        "attempt_count": job.attempt_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _error_code(exc: Exception, fallback: str) -> str:
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        value = str(details.get("error_code") or "").strip()
        if value:
            return value[:64]
    return fallback


def _error_message(exc: Exception, fallback: str) -> str:
    text = str(exc or "").strip()
    return text[:500] if text else fallback
