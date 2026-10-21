"""Admin period-scoped plan quota top-ups (limit bumps for current billing period)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import ValidationError
from platform_api.models.domain import Plan
from platform_api.services.billing_period_service import (
    ActiveSubscriptionContext,
    period_end_for_subscription,
    period_start_for_subscription,
)
from platform_api.services.billing_calendar import billing_today
from platform_api.services.subscription_entitlement_service import (
    effective_monthly_limit_for_operation,
)

QUOTA_KINDS = frozenset({"draft", "music", "image", "video", "merge"})

# Product / display field → stored quota_kind
_QUOTA_FIELD_TO_KIND: dict[str, str] = {
    "songs": "music",
    "music": "music",
    "drafts": "draft",
    "draft": "draft",
    "images": "image",
    "image": "image",
    "videos": "video",
    "video": "video",
    "merges": "merge",
    "merge": "merge",
}

# quota_kind → operation_type passed to effective_monthly_limit_for_operation
_KIND_TO_OPERATION: dict[str, str] = {
    "music": "music",
    "draft": "draft",
    "image": "background_image",
    "video": "video",
    "merge": "video_merge",
}


class QuotaTopupRepoProtocol(Protocol):
    async def add_topup(
        self,
        *,
        user_id: UUID,
        license_id: UUID | None,
        period_start: date,
        quota_kind: str,
        extra_units: int,
        reason: str,
        created_by: UUID,
    ) -> UUID: ...

    async def sum_extra_units(
        self,
        user_id: UUID,
        period_start: date,
        quota_kind: str,
    ) -> int: ...

    async def sum_extras_for_period(
        self,
        user_id: UUID,
        period_start: date,
    ) -> dict[str, int]: ...


class PlanRepoProtocol(Protocol):
    async def get_user_active_subscription_context(
        self, user_id: UUID
    ) -> ActiveSubscriptionContext | None: ...

    async def get_user_active_plan(self, user_id: UUID) -> Plan | None: ...


class UsageCountRepoProtocol(Protocol):
    async def get_monthly_count(
        self, user_id: UUID, operation_type: str, period_start: date
    ) -> int: ...


def normalize_quota_kind(value: str) -> str:
    """Map UI / op aliases to stored quota_kind."""
    key = (value or "").strip().lower()
    kind = _QUOTA_FIELD_TO_KIND.get(key)
    if kind is None:
        raise ValidationError(
            message=f"Invalid quota_kind: {value!r}.",
            details={
                "quota_kind": value,
                "allowed": sorted(QUOTA_KINDS),
            },
        )
    return kind


def quota_kind_for_operation(operation_type: str) -> str | None:
    """Return stored quota_kind for an enforcement operation_type, or None."""
    key = (operation_type or "").strip().lower()
    if key in (
        "music",
        "music_generation",
        "batch_generation",
        "songs",
    ):
        return "music"
    if key in ("draft", "lyric", "title", "album", "lyrics", "drafts"):
        return "draft"
    if key in (
        "image_generation",
        "background_image",
        "thumbnail_image",
        "channel_setup",
        "images",
        "image",
    ):
        return "image"
    if key in ("video", "video_generation", "video_export", "video_manual", "videos"):
        return "video"
    if key in ("video_merge", "merge", "auto_merge", "merges"):
        return "merge"
    return None


def quota_kind_for_display_field(quota_field: str) -> str | None:
    return _QUOTA_FIELD_TO_KIND.get((quota_field or "").strip().lower())


@dataclass(frozen=True, slots=True)
class QuotaKindStatus:
    quota_kind: str
    base_limit: int | None
    topup_extra: int
    effective_limit: int | None
    used: int
    remaining: int | None


@dataclass(frozen=True, slots=True)
class AdminQuotaPeriodSnapshot:
    period_start: date | None
    period_end: date | None
    plan_name: str | None
    kinds: dict[str, QuotaKindStatus]


class QuotaTopupService:
    """Grant and resolve period-scoped quota limit bumps."""

    def __init__(
        self,
        topup_repo: QuotaTopupRepoProtocol,
        plan_repo: PlanRepoProtocol,
        usage_repo: UsageCountRepoProtocol | None = None,
    ) -> None:
        self._topup_repo = topup_repo
        self._plan_repo = plan_repo
        self._usage_repo = usage_repo

    async def resolve_context(
        self, user_id: UUID
    ) -> ActiveSubscriptionContext | None:
        getter = getattr(self._plan_repo, "get_user_active_subscription_context", None)
        if getter is not None:
            ctx = await getter(user_id)
            if ctx is not None:
                return ctx
        plan = await self._plan_repo.get_user_active_plan(user_id)
        if plan is None:
            return None
        return ActiveSubscriptionContext(
            plan=plan,
            license_id=UUID(int=0),
            activated_at=None,
        )

    def period_bounds(
        self,
        ctx: ActiveSubscriptionContext,
        *,
        reference_date: date | None = None,
    ) -> tuple[date, date]:
        today = reference_date or billing_today()
        period_start = period_start_for_subscription(
            plan=ctx.plan,
            activated_at=ctx.activated_at,
            reference_date=today,
        )
        period_end = period_end_for_subscription(
            plan=ctx.plan,
            period_start=period_start,
        )
        return period_start, period_end

    async def extra_for(
        self,
        user_id: UUID,
        period_start: date,
        quota_kind: str,
    ) -> int:
        kind = normalize_quota_kind(quota_kind)
        return int(
            await self._topup_repo.sum_extra_units(user_id, period_start, kind) or 0
        )

    async def extras_for_period(
        self,
        user_id: UUID,
        period_start: date,
    ) -> dict[str, int]:
        """All quota-kind extras for one billing period."""
        return await self._topup_repo.sum_extras_for_period(user_id, period_start)

    async def effective_monthly_limit_with_topup(
        self,
        *,
        user_id: UUID,
        plan: Plan,
        addon_slots: int,
        operation_type: str,
        period_start: date,
    ) -> int | None:
        """Plan monthly limit + period top-up extras for this operation."""
        base = effective_monthly_limit_for_operation(plan, addon_slots, operation_type)
        if base is None:
            return None
        kind = quota_kind_for_operation(operation_type)
        if kind is None:
            return int(base)
        extra = await self.extra_for(user_id, period_start, kind)
        return int(base) + int(extra)

    async def grant(
        self,
        *,
        user_id: UUID,
        quota_kind: str,
        amount: int,
        reason: str,
        admin_id: UUID,
    ) -> dict[str, Any]:
        """Append a period top-up for the user's current billing period."""
        kind = normalize_quota_kind(quota_kind)
        units = int(amount)
        if units <= 0:
            raise ValidationError(
                message="Top-up amount must be a positive integer.",
                details={"amount": amount},
            )
        reason_text = (reason or "").strip()
        if not reason_text:
            raise ValidationError(
                message="Reason is required.",
                details={"reason": reason},
            )

        ctx = await self.resolve_context(user_id)
        if ctx is None:
            raise ValidationError(
                message="User has no active subscription plan to top up.",
                details={"user_id": str(user_id)},
            )

        period_start, period_end = self.period_bounds(ctx)
        addon_slots = int(getattr(ctx, "profile_addon_slots", 0) or 0)
        op = _KIND_TO_OPERATION[kind]
        base_limit = effective_monthly_limit_for_operation(ctx.plan, addon_slots, op)
        if base_limit is None:
            raise ValidationError(
                message="Cannot top up an unlimited quota.",
                details={"quota_kind": kind},
            )

        license_id = ctx.license_id
        if license_id is not None and license_id.int == 0:
            license_id = None

        topup_id = await self._topup_repo.add_topup(
            user_id=user_id,
            license_id=license_id,
            period_start=period_start,
            quota_kind=kind,
            extra_units=units,
            reason=reason_text,
            created_by=admin_id,
        )
        topup_extra = await self.extra_for(user_id, period_start, kind)
        effective = int(base_limit) + int(topup_extra)
        used = 0
        if self._usage_repo is not None:
            used = await self._used_for_kind(user_id, kind, period_start, period_end)

        return {
            "id": str(topup_id),
            "user_id": str(user_id),
            "quota_kind": kind,
            "amount": units,
            "reason": reason_text,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "base_limit": int(base_limit),
            "topup_extra": int(topup_extra),
            "effective_limit": effective,
            "used": used,
            "remaining": max(0, effective - used),
        }

    async def build_period_snapshot(
        self,
        user_id: UUID,
    ) -> AdminQuotaPeriodSnapshot:
        ctx = await self.resolve_context(user_id)
        if ctx is None:
            empty = {
                kind: QuotaKindStatus(
                    quota_kind=kind,
                    base_limit=None,
                    topup_extra=0,
                    effective_limit=None,
                    used=0,
                    remaining=None,
                )
                for kind in sorted(QUOTA_KINDS)
            }
            return AdminQuotaPeriodSnapshot(
                period_start=None,
                period_end=None,
                plan_name=None,
                kinds=empty,
            )

        period_start, period_end = self.period_bounds(ctx)
        addon_slots = int(getattr(ctx, "profile_addon_slots", 0) or 0)
        extras = await self._topup_repo.sum_extras_for_period(user_id, period_start)
        kinds: dict[str, QuotaKindStatus] = {}
        for kind in sorted(QUOTA_KINDS):
            op = _KIND_TO_OPERATION[kind]
            base = effective_monthly_limit_for_operation(ctx.plan, addon_slots, op)
            extra = int(extras.get(kind, 0) or 0)
            effective = None if base is None else int(base) + extra
            used = 0
            if self._usage_repo is not None:
                used = await self._used_for_kind(user_id, kind, period_start, period_end)
            remaining = None if effective is None else max(0, effective - used)
            kinds[kind] = QuotaKindStatus(
                quota_kind=kind,
                base_limit=None if base is None else int(base),
                topup_extra=extra,
                effective_limit=effective,
                used=used,
                remaining=remaining,
            )
        return AdminQuotaPeriodSnapshot(
            period_start=period_start,
            period_end=period_end,
            plan_name=ctx.plan.name or None,
            kinds=kinds,
        )

    async def _used_for_kind(
        self,
        user_id: UUID,
        kind: str,
        period_start: date,
        period_end: date | None = None,
    ) -> int:
        assert self._usage_repo is not None
        if kind == "music":
            # Authoritative, matching enforcement: ``_enforce_plan_quotas`` counts
            # real ``songs`` rows, not the incremental ``usage_tracking`` counter
            # (which the credits-only v3 charge path no longer increments — see
            # docs/bugs/2026-10-05-plan-quota-enforcement-bypass.md). Fall back to
            # the counter when the authoritative query is unavailable.
            songs_counter = getattr(
                self._usage_repo, "count_generated_songs_for_period", None
            )
            if songs_counter is not None and period_end is not None:
                return int(await songs_counter(user_id, period_start, period_end) or 0)
            return int(
                await self._usage_repo.get_monthly_count(user_id, "music", period_start)
                or 0
            )
        if kind == "draft":
            return int(
                await self._usage_repo.get_monthly_count(user_id, "draft", period_start)
                or 0
            )
        if kind == "image":
            used = int(
                await self._usage_repo.get_monthly_count(
                    user_id, "background_image", period_start
                )
                or 0
            )
            used += int(
                await self._usage_repo.get_monthly_count(
                    user_id, "thumbnail_image", period_start
                )
                or 0
            )
            return used
        if kind == "video":
            used = int(
                await self._usage_repo.get_monthly_count(user_id, "video", period_start)
                or 0
            )
            used += int(
                await self._usage_repo.get_monthly_count(
                    user_id, "video_manual", period_start
                )
                or 0
            )
            return used
        if kind == "merge":
            return int(
                await self._usage_repo.get_monthly_count(
                    user_id, "video_merge", period_start
                )
                or 0
            )
        return 0


def snapshot_to_dict(snapshot: AdminQuotaPeriodSnapshot) -> dict[str, Any]:
    """Serialize snapshot for admin API / user details."""
    kinds_out: dict[str, Any] = {}
    for kind, status in snapshot.kinds.items():
        kinds_out[kind] = {
            "quota_kind": status.quota_kind,
            "base_limit": status.base_limit,
            "topup_extra": status.topup_extra,
            "effective_limit": status.effective_limit,
            "used": status.used,
            "remaining": status.remaining,
        }
    return {
        "period_start": snapshot.period_start.isoformat()
        if snapshot.period_start
        else None,
        "period_end": snapshot.period_end.isoformat() if snapshot.period_end else None,
        "plan_name": snapshot.plan_name,
        "kinds": kinds_out,
    }
