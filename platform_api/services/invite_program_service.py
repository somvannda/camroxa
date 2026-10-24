"""Invite-a-friend referral program for music.camxora.com.

A user gets a personal referral code. When a brand-new account signs up with it
and later pays for their **first** credit pack, both sides receive a reward
(percentage of the purchased credits or a fixed amount, configured in the admin
portal). The ``referrals`` row is the idempotency guard: it is claimed exactly
once, so retried webhooks and repeated status polls cannot double-pay.
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from platform_api.exceptions import ValidationError
from platform_api.repositories.credit_repo import CreditRepository, MAX_WALLET_BALANCE
from platform_api.services.credit_units import credits_to_units
from platform_api.services.v3.store import V3BillingStore

logger = logging.getLogger(__name__)

INVITE_SETTINGS_KEY = "invite_program"
INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_FIXED_REWARD = 1_000_000


class AsyncPGSource(Protocol):
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class RewardRule:
    mode: str
    value: float


@dataclass(frozen=True, slots=True)
class InviteSettings:
    enabled: bool
    inviter: RewardRule
    invitee: RewardRule


DEFAULT_INVITE_SETTINGS = InviteSettings(
    enabled=True,
    inviter=RewardRule(mode="percent", value=15.0),
    invitee=RewardRule(mode="percent", value=15.0),
)


def _clamp(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number or number in (float("inf"), float("-inf")):
        return fallback
    return min(maximum, max(minimum, number))


def _coerce_rule(value: Any, fallback: RewardRule) -> RewardRule:
    data = value if isinstance(value, dict) else {}
    mode = "fixed" if str(data.get("mode") or "").lower() == "fixed" else (
        "percent" if str(data.get("mode") or "").lower() == "percent" else fallback.mode
    )
    maximum = 100.0 if mode == "percent" else float(MAX_FIXED_REWARD)
    return RewardRule(mode=mode, value=_clamp(data.get("value"), fallback.value, 0.0, maximum))


def coerce_invite_settings(value: Any) -> InviteSettings:
    """Parse a stored JSON document (or a patch) into safe settings."""
    data: Any = value
    if isinstance(value, str) and value.strip():
        try:
            data = json.loads(value)
        except (TypeError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    enabled = data.get("enabled")
    return InviteSettings(
        enabled=enabled if isinstance(enabled, bool) else DEFAULT_INVITE_SETTINGS.enabled,
        inviter=_coerce_rule(data.get("inviter"), DEFAULT_INVITE_SETTINGS.inviter),
        invitee=_coerce_rule(data.get("invitee"), DEFAULT_INVITE_SETTINGS.invitee),
    )


def merge_invite_settings(current: InviteSettings, patch: Any) -> InviteSettings:
    """Apply an admin patch, rejecting malformed or out-of-range values."""
    if not isinstance(patch, dict):
        raise ValidationError(message="Invite settings patch must be an object.")

    enabled = current.enabled
    if "enabled" in patch:
        if not isinstance(patch["enabled"], bool):
            raise ValidationError(message="invite_program.enabled must be a boolean.")
        enabled = patch["enabled"]

    rules: dict[str, RewardRule] = {"inviter": current.inviter, "invitee": current.invitee}
    for side in ("inviter", "invitee"):
        if side not in patch:
            continue
        side_patch = patch[side]
        if not isinstance(side_patch, dict):
            raise ValidationError(message=f"invite_program.{side} must be an object.")
        mode = rules[side].mode
        if "mode" in side_patch:
            if side_patch["mode"] not in ("percent", "fixed"):
                raise ValidationError(
                    message=f"invite_program.{side}.mode must be 'percent' or 'fixed'."
                )
            mode = str(side_patch["mode"])
        value = rules[side].value
        if "value" in side_patch:
            raw = side_patch["value"]
            if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw < 0:
                raise ValidationError(
                    message=f"invite_program.{side}.value must be a non-negative number."
                )
            value = float(raw)
        maximum = 100.0 if mode == "percent" else float(MAX_FIXED_REWARD)
        if value > maximum:
            raise ValidationError(
                message=(
                    f"invite_program.{side}.value must be at most 100 percent."
                    if mode == "percent"
                    else f"invite_program.{side}.value must be at most {MAX_FIXED_REWARD} credits."
                )
            )
        rules[side] = RewardRule(mode=mode, value=value)

    return InviteSettings(enabled=enabled, inviter=rules["inviter"], invitee=rules["invitee"])


def invite_reward_credits(rule: RewardRule, purchased_credits: int) -> int:
    """Credits owed for one side, in display credits."""
    if rule.value <= 0 or purchased_credits <= 0:
        return 0
    if rule.mode == "fixed":
        return max(0, int(round(rule.value)))
    percent = min(100.0, rule.value)
    return max(1, int(purchased_credits * percent // 100))


def serialize_invite_settings(settings: InviteSettings) -> dict[str, Any]:
    return {
        "enabled": settings.enabled,
        "inviter": {"mode": settings.inviter.mode, "value": settings.inviter.value},
        "invitee": {"mode": settings.invitee.mode, "value": settings.invitee.value},
    }


async def load_invite_settings(db: AsyncPGSource) -> InviteSettings:
    row = await db.fetchrow(
        "SELECT value FROM system_settings WHERE key = $1",
        INVITE_SETTINGS_KEY,
    )
    return coerce_invite_settings(row["value"] if row is not None else None)


async def save_invite_settings(db: AsyncPGSource, settings: InviteSettings) -> None:
    await db.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ($1, 'json', $2, NOW())
        ON CONFLICT (key) DO UPDATE
            SET value = $2, value_type = 'json', updated_at = NOW()
        """,
        INVITE_SETTINGS_KEY,
        json.dumps(serialize_invite_settings(settings)),
    )


def normalize_referral_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    code = "".join(ch for ch in value.strip().upper() if ch.isalnum())
    return code if 4 <= len(code) <= 32 else None


def _generate_referral_code(length: int = 8) -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(length))


async def ensure_referral_code(db: AsyncPGSource, user_id: Any) -> str:
    """Return the user's code, creating one on first use (race-safe)."""
    row = await db.fetchrow("SELECT referral_code FROM users WHERE id = $1", user_id)
    if row is not None and row["referral_code"]:
        return str(row["referral_code"])

    for _ in range(6):
        try:
            updated = await db.fetchrow(
                """
                UPDATE users
                   SET referral_code = $1
                 WHERE id = $2 AND referral_code IS NULL
                RETURNING referral_code
                """,
                _generate_referral_code(),
                user_id,
            )
            if updated is not None and updated["referral_code"]:
                return str(updated["referral_code"])
        except Exception as exc:  # unique_violation is the only expected failure
            if getattr(exc, "sqlstate", None) != "23505":
                raise
        row = await db.fetchrow("SELECT referral_code FROM users WHERE id = $1", user_id)
        if row is not None and row["referral_code"]:
            return str(row["referral_code"])

    raise ValidationError(message="Could not allocate a referral code. Please retry.")


async def link_referral(
    db: AsyncPGSource,
    *,
    invitee_id: Any,
    invitee_email: str,
    referral_code: Any,
    invited_ip: str | None = None,
) -> bool:
    """Link a brand-new account to an inviter. Unknown/self codes are ignored."""
    code = normalize_referral_code(referral_code)
    if not code:
        return False

    inviter = await db.fetchrow(
        """
        SELECT id, LOWER(email) AS email
        FROM users
        WHERE referral_code = $1
          AND deleted_at IS NULL
          AND status = 'active'
        LIMIT 1
        """,
        code,
    )
    if inviter is None:
        return False
    if str(inviter["id"]) == str(invitee_id):
        return False
    if str(inviter["email"]).lower() == invitee_email.strip().lower():
        return False

    inserted = await db.fetchrow(
        """
        INSERT INTO referrals (inviter_id, invitee_id, invitee_email, code, invited_ip)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (invitee_id) DO NOTHING
        RETURNING id
        """,
        inviter["id"],
        invitee_id,
        invitee_email,
        code,
        invited_ip,
    )
    return inserted is not None


async def _grant_reward(
    db: AsyncPGSource,
    *,
    user_id: Any,
    reward_credits: int,
    invite_id: Any,
    side: str,
) -> None:
    if reward_credits <= 0:
        return
    balance = await db.fetchval(
        "SELECT balance FROM credit_wallets WHERE user_id = $1",
        user_id,
    )
    room = MAX_WALLET_BALANCE - int(balance or 0)
    units = min(credits_to_units(reward_credits), max(0, room))
    if units <= 0:
        logger.warning("invite reward skipped (wallet full) user=%s invite=%s", user_id, invite_id)
        return
    repo = CreditRepository(pool=db)
    ref_id = f"invite:{invite_id}:{side}"
    await repo.add_credits(
        user_id=user_id,
        amount=units,
        reason="invite_reward",
        ref_id=ref_id,
        metadata={
            "invite_id": str(invite_id),
            "reward_credits": reward_credits,
            "side": side,
        },
    )
    # Universal wallet credits, but on the same 30-day term as pack credits.
    # The stable ref_id makes the lot idempotent across payment retries.
    await V3BillingStore(pool=db).insert_referral_lot_if_absent(
        user_id=user_id,
        amount_units=units,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        ref_id=ref_id,
    )


async def apply_referral_reward(
    db: AsyncPGSource,
    *,
    invitee_id: Any,
    purchased_credits: int,
    qualifying_ref: str,
) -> None:
    """Pay both sides when ``invitee_id`` makes their first paid pack purchase.

    Caller must provide a connection that is already inside the purchase
    transaction (or a pool for a standalone idempotent retry). The row lock plus
    the guarded status update make this exactly-once.
    """
    invite = await db.fetchrow(
        """
        SELECT id, inviter_id, status
        FROM referrals
        WHERE invitee_id = $1 AND status = 'pending'
        FOR UPDATE
        """,
        invitee_id,
    )
    if invite is None:
        return

    settings = await load_invite_settings(db)
    if not settings.enabled:
        await db.execute(
            """
            UPDATE referrals
               SET status = 'skipped',
                   qualifying_ref = $2,
                   purchased_credits = $3,
                   rewarded_at = NOW()
             WHERE id = $1 AND status = 'pending'
            """,
            invite["id"],
            qualifying_ref,
            int(purchased_credits),
        )
        return

    inviter_reward = invite_reward_credits(settings.inviter, int(purchased_credits))
    invitee_reward = invite_reward_credits(settings.invitee, int(purchased_credits))

    # Grant first, then close the invite. If a grant fails, the caller's
    # transaction rolls back and the invite stays pending for a retry; the
    # stable per-side ref_id keeps a successful side from paying twice.
    await _grant_reward(
        db,
        user_id=invite["inviter_id"],
        reward_credits=inviter_reward,
        invite_id=invite["id"],
        side="inviter",
    )
    await _grant_reward(
        db,
        user_id=invitee_id,
        reward_credits=invitee_reward,
        invite_id=invite["id"],
        side="invitee",
    )

    await db.execute(
        """
        UPDATE referrals
           SET status = 'rewarded',
               qualifying_ref = $2,
               purchased_credits = $3,
               inviter_reward = $4,
               invitee_reward = $5,
               rewarded_at = NOW()
         WHERE id = $1 AND status = 'pending'
        """,
        invite["id"],
        qualifying_ref,
        int(purchased_credits),
        inviter_reward,
        invitee_reward,
    )


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not local or not domain:
        return "***"
    return f"{local[0]}{'*' * max(1, len(local) - 1)}@{domain}"


async def get_user_invite_view(db: AsyncPGSource, *, user_id: Any) -> dict[str, Any]:
    code = await ensure_referral_code(db, user_id)
    settings = await load_invite_settings(db)
    summary = await db.fetchrow(
        """
        SELECT COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE status = 'pending')::int AS pending,
               COUNT(*) FILTER (WHERE status = 'rewarded')::int AS rewarded,
               COALESCE(SUM(inviter_reward) FILTER (WHERE status = 'rewarded'), 0)::int
                   AS credits_earned
        FROM referrals
        WHERE inviter_id = $1
        """,
        user_id,
    )
    rows = await db.fetch(
        """
        SELECT id, invitee_email, status, purchased_credits,
               inviter_reward AS reward, created_at, rewarded_at
        FROM referrals
        WHERE inviter_id = $1
        ORDER BY created_at DESC
        LIMIT 50
        """,
        user_id,
    )
    return {
        "enabled": settings.enabled,
        "settings": serialize_invite_settings(settings),
        "code": code,
        "share_path": f"/register?ref={code}",
        "summary": {
            "total": int(summary["total"] or 0) if summary else 0,
            "pending": int(summary["pending"] or 0) if summary else 0,
            "rewarded": int(summary["rewarded"] or 0) if summary else 0,
            "credits_earned": int(summary["credits_earned"] or 0) if summary else 0,
        },
        "invites": [
            {
                "id": str(row["id"]),
                "invitee_email": mask_email(str(row["invitee_email"])),
                "status": str(row["status"]),
                "purchased_credits": row["purchased_credits"],
                "reward": int(row["reward"] or 0),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "rewarded_at": row["rewarded_at"].isoformat() if row["rewarded_at"] else None,
            }
            for row in rows
        ],
    }


async def list_admin_referrals(
    db: AsyncPGSource,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 25)))
    filters: list[str] = []
    params: list[Any] = []
    if status in ("pending", "rewarded", "skipped", "rejected"):
        params.append(status)
        filters.append(f"r.status = ${len(params)}")
    if query:
        params.append(f"%{query.strip().lower()}%")
        filters.append(
            "(LOWER(inviter.email) LIKE ${idx})".format(idx=len(params))
            + " OR LOWER(COALESCE(inviter.display_name, '')) LIKE ${idx}".format(idx=len(params))
            + " OR LOWER(r.invitee_email) LIKE ${idx}".format(idx=len(params))
            + " OR LOWER(r.code) LIKE ${idx}".format(idx=len(params))
        )
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    total_row = await db.fetchrow(
        f"""
        SELECT COUNT(*)::int AS total
        FROM referrals r
        JOIN users inviter ON inviter.id = r.inviter_id
        {where}
        """,
        *params,
    )
    rows = await db.fetch(
        f"""
        SELECT r.id, r.status, r.code, r.invitee_email, r.invited_ip,
               r.purchased_credits, r.inviter_reward, r.invitee_reward,
               r.qualifying_ref, r.created_at, r.rewarded_at,
               inviter.id AS inviter_id, inviter.email AS inviter_email,
               inviter.display_name AS inviter_name
        FROM referrals r
        JOIN users inviter ON inviter.id = r.inviter_id
        {where}
        ORDER BY r.created_at DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """,
        *params,
        page_size,
        (page - 1) * page_size,
    )
    summary = await db.fetchrow(
        """
        SELECT COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE status = 'pending')::int AS pending,
               COUNT(*) FILTER (WHERE status = 'rewarded')::int AS rewarded,
               COUNT(*) FILTER (WHERE status = 'skipped')::int AS skipped,
               COUNT(*) FILTER (WHERE status = 'rejected')::int AS rejected,
               COALESCE(SUM(inviter_reward) FILTER (WHERE status = 'rewarded'), 0)::int
                   AS inviter_credits,
               COALESCE(SUM(invitee_reward) FILTER (WHERE status = 'rewarded'), 0)::int
                   AS invitee_credits
        FROM referrals
        """
    )
    settings = await load_invite_settings(db)
    return {
        "rows": [
            {
                **{key: row[key] for key in (
                    "id", "status", "code", "invitee_email", "invited_ip",
                    "purchased_credits", "inviter_reward", "invitee_reward",
                    "inviter_id", "inviter_email", "inviter_name", "qualifying_ref",
                )},
                "id": str(row["id"]),
                "inviter_id": str(row["inviter_id"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "rewarded_at": row["rewarded_at"].isoformat() if row["rewarded_at"] else None,
            }
            for row in rows
        ],
        "total": int(total_row["total"] or 0) if total_row else 0,
        "page": page,
        "page_size": page_size,
        "settings": serialize_invite_settings(settings),
        "summary": {
            key: int(summary[key] or 0) if summary else 0
            for key in (
                "total", "pending", "rewarded", "skipped", "rejected",
                "inviter_credits", "invitee_credits",
            )
        },
    }


async def reject_referral(db: AsyncPGSource, invite_id: Any) -> bool:
    row = await db.fetchrow(
        "UPDATE referrals SET status = 'rejected' WHERE id = $1 AND status = 'pending' RETURNING id",
        invite_id,
    )
    return row is not None


async def restore_referral(db: AsyncPGSource, invite_id: Any) -> bool:
    row = await db.fetchrow(
        """
        UPDATE referrals
           SET status = 'pending',
               qualifying_ref = NULL,
               purchased_credits = NULL,
               inviter_reward = 0,
               invitee_reward = 0,
               rewarded_at = NULL
         WHERE id = $1 AND status IN ('rejected', 'skipped')
        RETURNING id
        """,
        invite_id,
    )
    return row is not None
