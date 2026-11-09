"""Creator Program workflow: applications, verification, and badges."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.repositories.creator_program_repo import CreatorProgramRepository
from platform_api.repositories.creator_repo import CreatorRepository

VERIFICATION_KINDS = {"identity", "authenticity", "business", "voice_consent"}
BADGES = {
    "verified",
    "founding",
    "top_creator",
    "partner",
    "label",
    "ai_artist",
    "ai_assisted",
    "staff",
}
REAPPLY_COOLDOWN_DAYS = 30
SLA_DAYS = 3
VERIFICATION_VALID_DAYS = 365


def _validate_application_payload(payload: dict[str, Any]) -> dict[str, Any]:
    pitch = str(payload.get("pitch") or "").strip()
    if not 50 <= len(pitch) <= 500:
        raise ValidationError(
            "pitch must be 50-500 characters.",
            details={"fields": {"pitch": "50-500 characters"}},
        )

    links = payload.get("links")
    if not isinstance(links, list) or not links:
        raise ValidationError(
            "At least one external link is required.",
            details={"fields": {"links": "at least one link"}},
        )
    if len(links) > 5:
        raise ValidationError(
            "links can contain at most 5 items.",
            details={"fields": {"links": "max 5 items"}},
        )
    cleaned_links = []
    for item in links:
        if not isinstance(item, dict):
            raise ValidationError(
                "Each link must have a label and url.",
                details={"fields": {"links": "invalid item"}},
            )
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        parsed = urlparse(url)
        if not label or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError(
                "Each link needs a label and an http(s) URL.",
                details={"fields": {"links": "label and url required"}},
            )
        cleaned_links.append({"label": label[:30], "url": url[:500]})

    track_ids = payload.get("track_ids") or []
    if not isinstance(track_ids, list) or len(track_ids) > 3:
        raise ValidationError(
            "track_ids must be a list of at most 3 items.",
            details={"fields": {"track_ids": "max 3 items"}},
        )

    if payload.get("rights_attested") is not True:
        raise ValidationError(
            "You must attest that you own or have cleared the rights.",
            details={"fields": {"rights_attested": "required"}},
        )

    requested_tier = str(payload.get("requested_tier") or "verified")
    if requested_tier != "verified":
        raise ValidationError(
            "Only Verified Creator applications are self-serve.",
            details={"fields": {"requested_tier": "partner is invite-only"}},
        )

    identity = payload.get("identity") or {}
    if not isinstance(identity, dict):
        identity = {}

    return {
        "pitch": pitch,
        "links": cleaned_links,
        "track_ids": [str(item) for item in track_ids],
        "rights_attested": True,
        "requested_tier": "verified",
        "identity": {
            "legal_name": str(identity.get("legal_name") or "").strip()[:120],
            "country_code": str(identity.get("country_code") or "").strip().upper()[:2],
            "date_of_birth": identity.get("date_of_birth"),
        },
    }


class CreatorProgramService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._repo = CreatorProgramRepository(pool)
        self._profiles = CreatorRepository(pool)

    # ------------------------------------------------------------------
    # Creator-facing
    # ------------------------------------------------------------------
    async def get_status(self, user_id: str) -> dict[str, Any]:
        profile = await self._profiles.get_by_user_id(user_id)
        application = await self._repo.get_latest_application(user_id)
        verifications = await self._repo.list_verifications(user_id)
        badges = await self._repo.list_active_badges(user_id)
        return {
            "profile": {
                "handle": profile.get("handle"),
                "tier": profile.get("tier"),
                "status": profile.get("status"),
            }
            if profile
            else None,
            "application": application,
            "verifications": verifications,
            "badges": badges,
        }

    async def submit_application(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        profile = await self._profiles.get_by_user_id(user_id)
        if profile is None:
            raise ValidationError(
                "Claim a creator profile before applying.",
                details={"fields": {"profile": "required"}},
            )

        cleaned = _validate_application_payload(payload)
        open_application = await self._repo.get_open_application(user_id)

        if open_application:
            if open_application["status"] != "changes_requested":
                raise DuplicateError("You already have an open application.")
            updated = await self._repo.resubmit_application(
                open_application["id"], payload=cleaned, sla_days=SLA_DAYS
            )
            return {"application": updated}

        latest = await self._repo.get_latest_application(user_id)
        if latest and latest["status"] == "rejected" and latest.get("reviewed_at"):
            next_allowed = latest["reviewed_at"] + timedelta(days=REAPPLY_COOLDOWN_DAYS)
            if next_allowed > datetime.now(timezone.utc):
                raise ValidationError(
                    "You can reapply 30 days after a rejection.",
                    details={
                        "fields": {"application": "cooldown"},
                        "next_allowed_at": next_allowed.isoformat(),
                    },
                )

        application = await self._repo.insert_application(
            user_id=user_id, payload=cleaned, sla_days=SLA_DAYS
        )
        return {"application": application}

    async def withdraw_application(self, user_id: str) -> dict[str, Any]:
        open_application = await self._repo.get_open_application(user_id)
        if open_application is None:
            raise NotFoundError("No open application.")
        updated = await self._repo.set_application_status(
            open_application["id"], status="withdrawn", reason="Withdrawn by creator."
        )
        return {"application": updated}

    async def submit_verification(
        self, user_id: str, *, kind: str, evidence_ref: str | None
    ) -> dict[str, Any]:
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind not in VERIFICATION_KINDS:
            raise ValidationError(
                "Unknown verification kind.",
                details={"fields": {"kind": "invalid"}},
            )
        evidence = str(evidence_ref or "").strip()
        if not evidence or len(evidence) > 1000:
            raise ValidationError(
                "evidence_ref is required (max 1000 characters).",
                details={"fields": {"evidence_ref": "required"}},
            )
        record = await self._repo.insert_verification(
            user_id=user_id, kind=normalized_kind, evidence_ref=evidence
        )
        return {"verification": record}

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    async def list_applications(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        items = await self._repo.list_applications(status=status, limit=limit, offset=offset)
        total = await self._repo.count_applications(status=status)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def decide_application(
        self,
        application_id: str,
        *,
        decision: str,
        reviewer_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        application = await self._repo.get_application(application_id)
        if application is None:
            raise NotFoundError("Application not found.")

        if decision == "approve":
            profile = await self._profiles.get_by_user_id(application["user_id"])
            if profile is None:
                raise ValidationError(
                    "The applicant has no creator profile.",
                    details={"fields": {"profile": "missing"}},
                )
            now = datetime.now(timezone.utc)
            expires = now + timedelta(days=VERIFICATION_VALID_DAYS)
            updated = await self._repo.set_application_status(
                application_id,
                status="approved",
                reviewer_id=reviewer_id,
                reason=reason or "Approved.",
            )
            await self._repo.set_profile_tier(
                application["user_id"],
                tier="verified",
                verified_at=now,
                verification_expires_at=expires,
            )
            await self._repo.grant_badge(
                user_id=application["user_id"],
                badge="verified",
                granted_by=reviewer_id,
                expires_at=expires,
                reason="Verified Creator application approved.",
            )
            return {"application": updated}

        if decision == "request_changes":
            if not reason:
                raise ValidationError(
                    "A reason is required when requesting changes.",
                    details={"fields": {"reason": "required"}},
                )
            updated = await self._repo.set_application_status(
                application_id,
                status="changes_requested",
                reviewer_id=reviewer_id,
                reason=reason,
            )
            return {"application": updated}

        if decision == "reject":
            if not reason:
                raise ValidationError(
                    "A reason is required when rejecting.",
                    details={"fields": {"reason": "required"}},
                )
            updated = await self._repo.set_application_status(
                application_id,
                status="rejected",
                reviewer_id=reviewer_id,
                reason=reason,
            )
            return {"application": updated}

        raise ValidationError(
            "decision must be approve, request_changes, or reject.",
            details={"fields": {"decision": "invalid"}},
        )

    async def list_pending_verifications(
        self, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        items = await self._repo.list_pending_verifications(limit=limit, offset=offset)
        return {"items": items, "limit": limit, "offset": offset}

    async def decide_verification(
        self,
        verification_id: str,
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
        expires = (
            datetime.now(timezone.utc) + timedelta(days=VERIFICATION_VALID_DAYS)
            if decision == "approve"
            else None
        )
        updated = await self._repo.decide_verification(
            verification_id,
            status="approved" if decision == "approve" else "rejected",
            reviewer_id=reviewer_id,
            reason=reason,
            expires_at=expires,
        )
        if not updated:
            raise NotFoundError("Verification not found.")
        return {"verification": updated}

    async def grant_badge(
        self,
        user_id: str,
        *,
        badge: str,
        reviewer_id: str,
        expires_at: datetime | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        normalized = str(badge or "").strip().lower()
        if normalized not in BADGES:
            raise ValidationError(
                "Unknown badge.",
                details={"fields": {"badge": "invalid"}},
            )
        profile = await self._profiles.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError("Creator profile not found.")

        record = await self._repo.grant_badge(
            user_id=user_id,
            badge=normalized,
            granted_by=reviewer_id,
            expires_at=expires_at,
            reason=reason,
        )
        if normalized == "verified":
            now = datetime.now(timezone.utc)
            await self._repo.set_profile_tier(
                user_id,
                tier="verified",
                verified_at=now,
                verification_expires_at=expires_at,
            )
        elif normalized == "partner":
            await self._repo.set_profile_tier(user_id, tier="partner")
        return {"badge": record}

    async def revoke_badge(self, user_id: str, *, badge: str, reason: str | None = None) -> dict[str, Any]:
        normalized = str(badge or "").strip().lower()
        if normalized not in BADGES:
            raise ValidationError(
                "Unknown badge.",
                details={"fields": {"badge": "invalid"}},
            )
        record = await self._repo.revoke_badge(user_id=user_id, badge=normalized, reason=reason)
        if not record:
            raise NotFoundError("Active badge not found.")
        if normalized in {"verified", "partner"}:
            await self._repo.set_profile_tier(
                user_id, tier="creator", verified_at=None, verification_expires_at=None
            )
        return {"badge": record}
