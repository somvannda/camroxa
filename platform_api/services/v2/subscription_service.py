"""Subscription service for web music plans."""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

import asyncpg

from platform_api.services.shared.cutluy_service import (
    CutLuyService,
    get_cutluy_service,
    normalize_cutluy_payment_status,
)
from platform_api.services.v2.payment_security import (
    paid_amount_matches,
    sanitize_music_web_return_url,
    validate_payment_id,
    webhook_user_matches,
)

logger = logging.getLogger(__name__)

# Monthly credit allowance refreshes every 30 days even on yearly billing plans.
MONTHLY_CREDIT_RESET_DAYS = 30

# Self-serve renewal opens this many days before the paid period ends. CutLuy is
# a one-time gateway, so renewal is a fresh charge.
RENEWAL_WINDOW_DAYS = 7


def next_credit_reset_at(
    *,
    billing_cycle: str,
    current_period_end: datetime,
    last_credit_reset: datetime,
) -> datetime:
    """When the subscriber's monthly credit pool next refreshes."""
    if billing_cycle == "yearly":
        return min(
            last_credit_reset + timedelta(days=MONTHLY_CREDIT_RESET_DAYS),
            current_period_end,
        )
    return current_period_end


def _parse_features(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


@dataclass
class Plan:
    """Plan model."""
    id: str
    name: str
    plan_type: str
    price_cents: int
    billing_cycle_days: int
    monthly_credits: int
    monthly_song_quota: int | None
    features: dict
    is_public: bool
    display_order: int
    daily_credits: int = 0
    pricing_features: list[str] = field(default_factory=list)
    pricing_credit_lines: list[str] = field(default_factory=list)


def _row_to_plan(row: dict) -> Plan:
    data = dict(row)
    data["id"] = str(data["id"])
    data["features"] = _parse_features(data.get("features"))
    data["daily_credits"] = int(data.get("daily_credits") or 0)
    data["monthly_credits"] = int(data.get("monthly_credits") or 0)
    from platform_api.services.pricing_display import normalize_pricing_features

    data["pricing_features"] = normalize_pricing_features(data.get("pricing_features"))
    data["pricing_credit_lines"] = normalize_pricing_features(data.get("pricing_credit_lines"))
    return Plan(**data)


@dataclass
class Subscription:
    """Subscription model."""
    id: str
    user_id: str
    plan_id: str
    status: str
    billing_cycle: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    monthly_credits_granted: int
    monthly_credits_used: int
    topup_credits_balance: int
    external_subscription_id: Optional[str]
    last_credit_reset: datetime | None = None


@dataclass
class CreditBalance:
    """Credit balance information."""
    monthly_granted: int
    monthly_used: int
    monthly_remaining: int
    topup_balance: int
    total_remaining: int
    reset_at: datetime


class SubscriptionService:
    """Service for managing web music subscriptions.
    
    Handles:
    - Plan queries
    - Subscription lifecycle (create, cancel)
    - CutLuy payment integration
    - Webhook processing
    - Monthly credit resets
    """
    
    def __init__(
        self,
        db,  # Database connection
        cutluy: Optional[CutLuyService] = None
    ):
        # Accept either the asyncpg adapter (fetch_one/fetch_all) or a raw asyncpg
        # pool. The startup maintenance loop passed the raw pool, so
        # process_due_subscriptions() raised AttributeError every 15 minutes and
        # silently skipped all renewals/expiry.
        if not hasattr(db, "fetch_all"):
            from platform_api.db.asyncpg_adapter import wrap_pool

            db = wrap_pool(db)
        self._db = db
        self._cutluy = cutluy or get_cutluy_service()
    
    # ─── Plan Management ────────────────────────────────────────────────
    
    async def get_plans(
        self,
        plan_type: str = "web_music",
        is_public: Optional[bool] = None
    ) -> list[Plan]:
        """Get subscription plans.
        
        Args:
            plan_type: 'web_music' or 'desktop_pro'
            is_public: Filter by visibility (None = all)
        
        Returns:
            List of plans
        """
        query = """
            SELECT 
                id, name, plan_type, price_cents, billing_cycle_days,
                monthly_credits, COALESCE(daily_credits, 0) AS daily_credits,
                monthly_song_limit AS monthly_song_quota, features,
                COALESCE(pricing_features, '{}'::text[]) AS pricing_features,
                COALESCE(pricing_credit_lines, '{}'::text[]) AS pricing_credit_lines,
                is_public, display_order
            FROM plans
            WHERE plan_type = $1
              AND is_active = true
        """
        params = [plan_type]
        
        if is_public is not None:
            query += " AND is_public = $2"
            params.append(is_public)
        
        query += " ORDER BY display_order, price_cents"
        
        rows = await self._db.fetch_all(query, *params)
        return [_row_to_plan(row) for row in rows]
    
    async def get_plan_by_id(self, plan_id: str) -> Optional[Plan]:
        """Get plan by ID."""
        row = await self._db.fetch_one("""
            SELECT 
                id, name, plan_type, price_cents, billing_cycle_days,
                monthly_credits, COALESCE(daily_credits, 0) AS daily_credits,
                monthly_song_limit AS monthly_song_quota, features,
                COALESCE(pricing_features, '{}'::text[]) AS pricing_features,
                COALESCE(pricing_credit_lines, '{}'::text[]) AS pricing_credit_lines,
                is_public, display_order
            FROM plans
            WHERE id = $1 AND is_active = true
        """, plan_id)
        
        return _row_to_plan(row) if row else None
    
    async def get_plan_by_name(self, name: str) -> Optional[Plan]:
        """Get plan by name (e.g., 'starter_monthly')."""
        row = await self._db.fetch_one("""
            SELECT 
                id, name, plan_type, price_cents, billing_cycle_days,
                monthly_credits, COALESCE(daily_credits, 0) AS daily_credits,
                monthly_song_limit AS monthly_song_quota, features,
                COALESCE(pricing_features, '{}'::text[]) AS pricing_features,
                COALESCE(pricing_credit_lines, '{}'::text[]) AS pricing_credit_lines,
                is_public, display_order
            FROM plans
            WHERE name = $1 AND is_active = true
        """, name)
        
        return _row_to_plan(row) if row else None
    
    # ─── Subscription Lifecycle ─────────────────────────────────────────
    
    async def get_user_subscription(self, user_id: str) -> Optional[dict]:
        """Get user's subscription as a dict for API responses."""
        row = await self._db.fetch_one("""
            SELECT 
                ws.id, ws.user_id, ws.plan_id, ws.status, ws.billing_cycle,
                ws.current_period_start, ws.current_period_end, ws.cancel_at_period_end,
                ws.monthly_credits_granted, ws.monthly_credits_used,
                ws.topup_credits_balance, ws.external_subscription_id,
                ws.last_credit_reset,
                ws.created_at, ws.cancelled_at,
                COALESCE(p.name, 'Pro') AS plan_name
            FROM web_subscriptions ws
            LEFT JOIN plans p ON ws.plan_id = p.id
            WHERE ws.user_id = $1
              AND ws.status = 'active'
              AND ws.current_period_end > NOW()
            ORDER BY ws.created_at DESC
            LIMIT 1
        """, user_id)

        if not row:
            return None

        if row["current_period_start"] is None or row["current_period_end"] is None:
            monthly_remaining = max(
                0,
                int(row["monthly_credits_granted"] or 0) - int(row["monthly_credits_used"] or 0),
            )
            result = dict(row)
            result["total_credits_available"] = monthly_remaining + int(
                row["topup_credits_balance"] or 0
            )
            return result

        subscription = Subscription(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            plan_id=str(row["plan_id"]),
            status=row["status"],
            billing_cycle=row["billing_cycle"],
            current_period_start=row["current_period_start"],
            current_period_end=row["current_period_end"],
            cancel_at_period_end=bool(row["cancel_at_period_end"]),
            monthly_credits_granted=int(row["monthly_credits_granted"] or 0),
            monthly_credits_used=int(row["monthly_credits_used"] or 0),
            topup_credits_balance=int(row["topup_credits_balance"] or 0),
            external_subscription_id=row.get("external_subscription_id"),
            last_credit_reset=row.get("last_credit_reset"),
        )

        await self.reset_quota_if_needed(subscription)

        refreshed = await self._db.fetch_one("""
            SELECT 
                ws.id, ws.user_id, ws.plan_id, ws.status, ws.billing_cycle,
                ws.current_period_start, ws.current_period_end, ws.cancel_at_period_end,
                ws.monthly_credits_granted, ws.monthly_credits_used,
                ws.topup_credits_balance, ws.external_subscription_id,
                ws.created_at, ws.cancelled_at,
                COALESCE(p.name, 'Pro') AS plan_name
            FROM web_subscriptions ws
            LEFT JOIN plans p ON ws.plan_id = p.id
            WHERE ws.id = $1
        """, subscription.id)

        if not refreshed:
            return None

        monthly_remaining = max(
            0,
            int(refreshed["monthly_credits_granted"] or 0)
            - int(refreshed["monthly_credits_used"] or 0),
        )
        result = dict(refreshed)
        result["total_credits_available"] = monthly_remaining + int(
            refreshed["topup_credits_balance"] or 0
        )
        return result

    async def _get_checkout_subscription_row(self, user_id: str) -> Optional[dict]:
        """Return the user's current web_subscriptions row, including pending checkout."""
        return await self._db.fetch_one(
            """
            SELECT id, status, plan_id
            FROM web_subscriptions
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    _REUSABLE_CHECKOUT_STATUSES = frozenset(
        {"pending", "expired", "cancelled", "past_due"}
    )

    async def _reset_subscription_row_to_pending(
        self,
        *,
        subscription_id: str,
        user_id: str,
        plan: Plan,
        billing_cycle: str,
        period_start: datetime,
        period_end: datetime,
    ) -> str:
        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET plan_id = $1,
                billing_cycle = $2,
                status = 'pending',
                current_period_start = $3,
                current_period_end = $4,
                monthly_credits_granted = $5,
                monthly_credits_used = 0,
                external_subscription_id = NULL,
                updated_at = NOW()
            WHERE id = $6 AND user_id = $7 AND status <> 'active'
            """,
            plan.id,
            billing_cycle,
            period_start,
            period_end,
            plan.monthly_credits,
            subscription_id,
            user_id,
        )
        return subscription_id

    async def _upsert_pending_subscription(
        self,
        *,
        user_id: str,
        plan: Plan,
        billing_cycle: str,
        period_start: datetime,
        period_end: datetime,
        existing: dict | None,
    ) -> str:
        if existing and existing.get("status") in self._REUSABLE_CHECKOUT_STATUSES:
            return await self._reset_subscription_row_to_pending(
                subscription_id=str(existing["id"]),
                user_id=user_id,
                plan=plan,
                billing_cycle=billing_cycle,
                period_start=period_start,
                period_end=period_end,
            )

        try:
            subscription_id = await self._db.fetch_val(
                """
                INSERT INTO web_subscriptions (
                    user_id, plan_id, status, billing_cycle,
                    current_period_start, current_period_end,
                    monthly_credits_granted, monthly_credits_used,
                    topup_credits_balance
                ) VALUES (
                    $1, $2, 'pending', $3, $4, $5, $6, 0, 0
                )
                RETURNING id
                """,
                user_id,
                plan.id,
                billing_cycle,
                period_start,
                period_end,
                plan.monthly_credits,
            )
            return str(subscription_id)
        except asyncpg.UniqueViolationError:
            reused = await self._get_checkout_subscription_row(user_id)
            if reused is None:
                raise
            if reused.get("status") == "active":
                raise ValueError("User already has an active subscription") from None
            return await self._reset_subscription_row_to_pending(
                subscription_id=str(reused["id"]),
                user_id=user_id,
                plan=plan,
                billing_cycle=billing_cycle,
                period_start=period_start,
                period_end=period_end,
            )
    
    async def create_subscription(
        self,
        user_id: str,
        plan_name: str,
        billing_cycle: str,  # 'monthly' or 'yearly'
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """Create new subscription and return payment URL.
        
        Args:
            user_id: User UUID
            plan_name: Plan name (e.g., 'starter_monthly')
            billing_cycle: 'monthly' or 'yearly'
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
        
        Returns:
            {
                "checkout_url": "https://cutluy.com/checkout/...",
                "payment_id": "pay_...",
                "expires_at": "..."
            }
        
        Raises:
            ValueError: If plan not found or user already has subscription
        """
        existing = await self._get_checkout_subscription_row(user_id)
        if existing and existing.get("status") == "active":
            raise ValueError("User already has an active subscription")

        # Get plan
        plan = await self.get_plan_by_name(plan_name)
        if not plan:
            raise ValueError(f"Plan not found: {plan_name}")
        self._assert_purchasable_plan(plan)
        success_url = sanitize_music_web_return_url(success_url)
        cancel_url = sanitize_music_web_return_url(cancel_url)

        # Validate billing cycle matches plan
        expected_cycle = "yearly" if plan.billing_cycle_days >= 365 else "monthly"
        if billing_cycle != expected_cycle:
            raise ValueError(
                f"Plan {plan_name} requires {expected_cycle} billing cycle"
            )

        # Calculate period dates
        period_start = datetime.utcnow()
        period_end = period_start + timedelta(days=plan.billing_cycle_days)

        subscription_id = await self._upsert_pending_subscription(
            user_id=user_id,
            plan=plan,
            billing_cycle=billing_cycle,
            period_start=period_start,
            period_end=period_end,
            existing=existing,
        )

        # Create CutLuy payment
        try:
            payment = await self._cutluy.create_subscription_payment(
                user_id=user_id,
                plan_name=plan.name,
                amount_cents=plan.price_cents,
                billing_cycle=billing_cycle,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "type": "subscription",
                    "subscription_id": str(subscription_id),
                    "plan_id": str(plan.id),
                    "monthly_credits": plan.monthly_credits,
                },
                db=self._db,
            )
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("CutLuy subscription payment failed for user %s", user_id)
            raise ValueError("Unable to start payment. Please try again.") from exc

        payment_id = payment.get("payment_id")
        if not payment_id:
            raise ValueError("CutLuy did not return a payment id")

        # Store external payment ID
        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET external_subscription_id = $1
            WHERE id = $2
            """,
            payment_id,
            subscription_id,
        )

        logger.info(
            "Created pending subscription %s for user %s",
            subscription_id,
            user_id,
        )

        return {
            "checkout_url": payment["checkout_url"],
            "payment_id": str(payment_id),
            "expires_at": payment.get("expires_at") or "",
            "qr_string": payment.get("qr_string") or "",
        }

    async def create_subscription_by_plan_id(
        self,
        user_id: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """Create subscription checkout using a plan UUID from the pricing UI."""
        plan = await self.get_plan_by_id(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        self._assert_purchasable_plan(plan)

        billing_cycle = "yearly" if plan.billing_cycle_days >= 365 else "monthly"
        return await self.create_subscription(
            user_id=user_id,
            plan_name=plan.name,
            billing_cycle=billing_cycle,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    def _assert_purchasable_plan(self, plan: Plan) -> None:
        if plan.plan_type != "web_music" or not plan.is_public:
            raise ValueError("Plan not available for purchase")
        if int(plan.price_cents or 0) < 1:
            raise ValueError("Plan is not purchasable")

    async def get_checkout_status(self, user_id: str, payment_id: str) -> dict[str, Any]:
        """Poll CutLuy and fulfill a web-music subscription checkout for this user."""
        try:
            payment_id = validate_payment_id(payment_id)
        except ValueError as exc:
            raise LookupError("Payment not found") from exc
        row = await self._db.fetch_one(
            """
            SELECT ws.id, ws.status, ws.monthly_credits_granted,
                   p.name AS plan_name, p.price_cents
            FROM web_subscriptions ws
            JOIN plans p ON ws.plan_id = p.id
            WHERE ws.user_id = $1
              AND ws.external_subscription_id = $2
            ORDER BY ws.created_at DESC
            LIMIT 1
            """,
            user_id,
            payment_id,
        )
        if not row:
            raise LookupError("Payment not found")

        plan_name = row["plan_name"]
        credits = int(row["monthly_credits_granted"] or 0)
        local_status = str(row["status"] or "")

        if local_status == "active":
            return {
                "status": "paid",
                "fulfilled": True,
                "plan_name": plan_name,
                "credits": credits,
            }
        if local_status in {"past_due", "cancelled", "expired"}:
            return {
                "status": "failed" if local_status == "past_due" else local_status,
                "fulfilled": False,
                "plan_name": plan_name,
                "credits": credits,
            }

        try:
            payload = await self._cutluy.get_payment_status(payment_id, db=self._db)
        except ValueError:
            logger.exception("CutLuy status check failed for payment %s", payment_id)
            return {
                "status": "pending",
                "fulfilled": False,
                "plan_name": plan_name,
                "credits": credits,
            }

        remote = normalize_cutluy_payment_status(payload.get("status"))
        if remote == "paid":
            if not paid_amount_matches(int(row["price_cents"] or 0), payload):
                logger.error(
                    "Refusing subscription fulfill: amount mismatch for payment %s",
                    payment_id,
                )
                return {
                    "status": "pending",
                    "fulfilled": False,
                    "plan_name": plan_name,
                    "credits": credits,
                }
            await self._fulfill_subscription_payment(
                payment_id=payment_id,
                subscription_id=str(row["id"]),
            )
            return {
                "status": "paid",
                "fulfilled": True,
                "plan_name": plan_name,
                "credits": credits,
            }
        if remote == "failed":
            await self._mark_subscription_terminal(str(row["id"]), "past_due")
            return {
                "status": "failed",
                "fulfilled": False,
                "plan_name": plan_name,
                "credits": credits,
            }
        if remote == "expired":
            await self._mark_subscription_terminal(str(row["id"]), "expired")
            return {
                "status": "expired",
                "fulfilled": False,
                "plan_name": plan_name,
                "credits": credits,
            }
        return {
            "status": "pending",
            "fulfilled": False,
            "plan_name": plan_name,
            "credits": credits,
        }

    async def _fulfill_subscription_payment(self, *, payment_id: str, subscription_id: str) -> None:
        """Activate a pending subscription after verified CutLuy payment. Idempotent."""
        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET status = 'active',
                last_payment_at = NOW()
            WHERE id = $1
              AND status = 'pending'
              AND external_subscription_id = $2
            """,
            subscription_id,
            payment_id,
        )
        logger.info("Activated subscription %s from payment %s", subscription_id, payment_id)
        await self._sync_v3_period_grant(subscription_id)

    async def _sync_v3_period_grant(self, subscription_id: str) -> None:
        row = await self._db.fetch_one(
            "SELECT user_id FROM web_subscriptions WHERE id = $1",
            subscription_id,
        )
        if not row or not row.get("user_id"):
            return
        from platform_api.services.v3.wallet_sync import sync_subscription_grant
        from uuid import UUID

        await sync_subscription_grant(UUID(str(row["user_id"])))

    async def _mark_subscription_terminal(self, subscription_id: str, status: str) -> None:
        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET status = $2
            WHERE id = $1
              AND status = 'pending'
            """,
            subscription_id,
            status,
        )

    # ─── Renewal (CutLuy is one-time; renewal is a fresh charge) ────────

    async def get_renewal_offer(self, user_id: str) -> dict | None:
        """Return the user's renewable plan and window, or None to renew nothing."""
        row = await self._db.fetch_one(
            """
            SELECT ws.id, ws.plan_id, ws.status, ws.billing_cycle,
                   ws.current_period_start, ws.current_period_end,
                   ws.cancel_at_period_end, ws.monthly_credits_granted,
                   p.name AS plan_name, p.price_cents, p.monthly_credits,
                   p.billing_cycle_days
            FROM web_subscriptions ws
            JOIN plans p ON p.id = ws.plan_id
            WHERE ws.user_id = $1
            ORDER BY ws.created_at DESC
            LIMIT 1
            """,
            user_id,
        )
        if not row:
            return None
        price_cents = int(row["price_cents"] or 0)
        if price_cents <= 0:
            return None
        now = datetime.now(timezone.utc)
        end = row["current_period_end"]
        expired = end is None or end <= now
        days_left = 0 if expired else max(0, (end - now).days)
        renewable = expired or days_left <= RENEWAL_WINDOW_DAYS
        opens_in_days = None if renewable else days_left - RENEWAL_WINDOW_DAYS
        return {
            "eligible": True,
            "subscription_id": str(row["id"]),
            "plan_id": str(row["plan_id"]),
            "plan_name": row["plan_name"],
            "price_cents": price_cents,
            "billing_cycle": row["billing_cycle"],
            "current_period_end": end,
            "days_left": days_left,
            "expired": expired,
            "renewable": renewable,
            "renewal_opens_in_days": opens_in_days,
            "renewal_window_days": RENEWAL_WINDOW_DAYS,
        }

    async def create_renewal_checkout(
        self, *, user_id: str, success_url: str, cancel_url: str
    ) -> dict:
        """Start a CutLuy checkout for the next period of the user's own plan."""
        offer = await self.get_renewal_offer(user_id)
        if offer is None:
            raise ValueError("No renewable plan was found for this account.")
        if not offer["renewable"]:
            raise ValueError(
                f"Renewal opens {RENEWAL_WINDOW_DAYS} days before your plan ends."
            )
        plan = await self.get_plan_by_id(offer["plan_id"])
        if plan is None:
            raise ValueError("Plan not found")
        payment = await self._cutluy.create_subscription_payment(
            user_id=user_id,
            plan_name=plan.name,
            amount_cents=plan.price_cents,
            billing_cycle=offer["billing_cycle"],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "subscription",
                "renewal": True,
                "subscription_id": offer["subscription_id"],
                "plan_id": str(plan.id),
                "monthly_credits": plan.monthly_credits,
            },
            db=self._db,
        )
        payment_id = payment.get("payment_id")
        if not payment_id:
            raise ValueError("CutLuy did not return a payment id")
        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET pending_renewal_payment_id = $1
            WHERE id = $2 AND user_id = $3
            """,
            payment_id,
            offer["subscription_id"],
            user_id,
        )
        return {
            "checkout_url": payment["checkout_url"],
            "payment_id": str(payment_id),
            "expires_at": payment.get("expires_at") or "",
            "qr_string": payment.get("qr_string") or "",
            "plan_name": plan.name,
            "credits": plan.monthly_credits,
            "amount_cents": plan.price_cents,
        }

    async def get_renewal_status(self, user_id: str, payment_id: str) -> dict:
        """Poll CutLuy and extend the period on a verified renewal payment."""
        try:
            payment_id = validate_payment_id(payment_id)
        except ValueError as exc:
            raise LookupError("Payment not found") from exc
        row = await self._db.fetch_one(
            """
            SELECT ws.id, ws.plan_id, ws.status, ws.current_period_start,
                   ws.current_period_end, ws.billing_cycle,
                   p.name AS plan_name, p.price_cents, p.monthly_credits,
                   p.billing_cycle_days
            FROM web_subscriptions ws
            JOIN plans p ON p.id = ws.plan_id
            WHERE ws.user_id = $1 AND ws.pending_renewal_payment_id = $2
            LIMIT 1
            """,
            user_id,
            payment_id,
        )
        if not row:
            raise LookupError("Payment not found")
        plan_name = row["plan_name"]
        credits = int(row["monthly_credits"] or 0)
        try:
            payload = await self._cutluy.get_payment_status(payment_id, db=self._db)
        except ValueError:
            return {"status": "pending", "fulfilled": False, "plan_name": plan_name, "credits": credits}
        remote = normalize_cutluy_payment_status(payload.get("status"))
        if remote == "paid":
            if not paid_amount_matches(int(row["price_cents"] or 0), payload):
                logger.error("Refusing renewal fulfill: amount mismatch for %s", payment_id)
                return {"status": "pending", "fulfilled": False, "plan_name": plan_name, "credits": credits}
            fulfilled = await self._fulfill_renewal(row, payment_id)
            return {"status": "paid", "fulfilled": fulfilled, "plan_name": plan_name, "credits": credits}
        if remote == "expired":
            await self._db.execute(
                "UPDATE web_subscriptions SET pending_renewal_payment_id = NULL WHERE id = $1",
                row["id"],
            )
            return {"status": "expired", "fulfilled": False, "plan_name": plan_name, "credits": credits}
        if remote == "failed":
            return {"status": "failed", "fulfilled": False, "plan_name": plan_name, "credits": credits}
        return {"status": "pending", "fulfilled": False, "plan_name": plan_name, "credits": credits}

    async def _fulfill_renewal(self, row: dict, payment_id: str) -> bool:
        """Extend the subscription by one paid cycle; idempotent per payment id."""
        plan = await self.get_plan_by_id(row["plan_id"])
        if plan is None:
            raise ValueError("Plan not found")
        now = datetime.now(timezone.utc)
        end = row["current_period_end"]
        # Stack early renewals from the current period end; expired starts now.
        base = end if end is not None and end > now else now
        new_end = base + timedelta(days=int(plan.billing_cycle_days or 30))
        updated = await self._db.fetch_one(
            """
            UPDATE web_subscriptions
            SET status = 'active',
                current_period_start = $1,
                current_period_end = $2,
                monthly_credits_used = 0,
                monthly_credits_granted = $3,
                last_credit_reset = $1,
                last_payment_at = NOW(),
                cancel_at_period_end = false,
                cancelled_at = NULL,
                renewal_reminder_sent_at = NULL,
                pending_renewal_payment_id = NULL
            WHERE id = $4 AND pending_renewal_payment_id = $5
            RETURNING id
            """,
            base,
            new_end,
            plan.monthly_credits,
            row["id"],
            payment_id,
        )
        if updated is None:
            return False
        await self._sync_v3_period_grant(str(row["id"]))
        logger.info(
            "Renewed web subscription %s: %s credits, period %s..%s",
            row["id"],
            plan.monthly_credits,
            base,
            new_end,
        )
        return True

    async def list_renewal_reminders_due(
        self, *, within_days: int = RENEWAL_WINDOW_DAYS
    ) -> list[dict]:
        """Active subscriptions entering the renewal window, not yet reminded."""
        return await self._db.fetch_all(
            """
            SELECT ws.id, ws.current_period_end,
                   u.email, u.display_name,
                   p.name AS plan_name, p.price_cents
            FROM web_subscriptions ws
            JOIN users u ON u.id = ws.user_id
            JOIN plans p ON p.id = ws.plan_id
            WHERE ws.status = 'active'
              AND ws.cancel_at_period_end = false
              AND ws.renewal_reminder_sent_at IS NULL
              AND ws.current_period_end > NOW()
              AND ws.current_period_end <= NOW() + ($1 * INTERVAL '1 day')
              AND COALESCE(p.price_cents, 0) > 0
              AND u.status = 'active'
            ORDER BY ws.current_period_end
            """,
            within_days,
        )

    async def mark_renewal_reminder_sent(self, subscription_id: str) -> None:
        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET renewal_reminder_sent_at = NOW()
            WHERE id = $1
            """,
            subscription_id,
        )

    async def cancel_subscription(
        self,
        user_id: str,
        cancel_at_period_end: bool = True
    ) -> bool:
        """Cancel user's subscription.
        
        Args:
            user_id: User UUID
            cancel_at_period_end: If True, cancel at end of billing period.
                                 If False, cancel immediately.
        
        Returns:
            True if cancelled successfully
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return False

        if subscription.get("status") != "active":
            return False

        external_id = subscription.get("external_subscription_id")
        if external_id:
            await self._cutluy.cancel_subscription(external_id)

        # Update subscription
        if cancel_at_period_end:
            await self._db.execute("""
                UPDATE web_subscriptions
                SET cancel_at_period_end = true,
                    cancelled_at = NOW()
                WHERE id = $1
            """, subscription["id"])

            logger.info(
                f"Subscription {subscription['id']} will cancel at "
                f"{subscription['current_period_end']}"
            )
        else:
            await self._db.execute("""
                UPDATE web_subscriptions
                SET status = 'cancelled',
                    cancel_at_period_end = false,
                    cancelled_at = NOW()
                WHERE id = $1
            """, subscription["id"])

            logger.info(f"Subscription {subscription['id']} cancelled immediately")
        
        return True
    
    # ─── Credit Management ──────────────────────────────────────────────
    
    async def get_credit_balance(self, user_id: str) -> Optional[CreditBalance]:
        """Get user's credit balance.
        
        Returns:
            CreditBalance with monthly and top-up credits
        """
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return None

        monthly_remaining = max(
            0,
            subscription["monthly_credits_granted"] - subscription["monthly_credits_used"]
        )

        last_reset = subscription.get("last_credit_reset") or subscription["current_period_start"]
        return CreditBalance(
            monthly_granted=subscription["monthly_credits_granted"],
            monthly_used=subscription["monthly_credits_used"],
            monthly_remaining=monthly_remaining,
            topup_balance=subscription["topup_credits_balance"],
            total_remaining=monthly_remaining + subscription["topup_credits_balance"],
            reset_at=next_credit_reset_at(
                billing_cycle=subscription["billing_cycle"],
                current_period_end=subscription["current_period_end"],
                last_credit_reset=last_reset,
            ),
        )
    
    async def _log_monthly_credit_reset(
        self,
        *,
        user_id: str,
        subscription_id: str,
        monthly_credits: int,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO credit_transactions (
                user_id, amount, direction, reason, ref_id
            ) VALUES (
                $1, $2, 'credit', 'monthly_reset', $3
            )
            """,
            user_id,
            monthly_credits,
            subscription_id,
        )

    async def _reset_yearly_monthly_allowance(
        self,
        subscription: Subscription,
        *,
        reset_at: datetime,
    ) -> bool:
        """Refresh monthly credits on a yearly plan without advancing billing."""
        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET monthly_credits_used = 0,
                last_credit_reset = $1
            WHERE id = $2
            """,
            reset_at,
            subscription.id,
        )
        await self._log_monthly_credit_reset(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            monthly_credits=subscription.monthly_credits_granted,
        )
        await self._sync_v3_period_grant(subscription.id)
        logger.info(
            "Reset monthly allowance for yearly subscription %s at %s",
            subscription.id,
            reset_at.isoformat(),
        )
        return True

    async def reset_quota_if_needed(self, subscription: Subscription) -> bool:
        """Reset monthly credits when the monthly allowance is due.

        CutLuy is a one-time (KHQR) gateway with no recurring charge, so a paid
        term is never extended here. When the period has ended the subscription
        expires and the user must start a new checkout; silently granting another
        period would renew every subscriber for free.
        """
        if subscription.status != "active":
            return False

        now = datetime.now(timezone.utc)
        last_reset = subscription.last_credit_reset or subscription.current_period_start

        if subscription.current_period_end <= now:
            await self._db.execute(
                """
                UPDATE web_subscriptions
                SET status = 'expired'
                WHERE id = $1 AND status = 'active'
                """,
                subscription.id,
            )
            logger.info(
                "Subscription %s expired at %s (CutLuy is not recurring; a new "
                "checkout is required to continue)",
                subscription.id,
                subscription.current_period_end,
            )
            return False

        if (
            subscription.billing_cycle == "yearly"
            and last_reset + timedelta(days=MONTHLY_CREDIT_RESET_DAYS) <= now
        ):
            return await self._reset_yearly_monthly_allowance(
                subscription,
                reset_at=now,
            )

        return False
    
    def _subscription_from_row(self, row: dict) -> Subscription:
        return Subscription(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            plan_id=str(row["plan_id"]),
            status=row["status"],
            billing_cycle=row["billing_cycle"],
            current_period_start=row["current_period_start"],
            current_period_end=row["current_period_end"],
            cancel_at_period_end=row["cancel_at_period_end"],
            monthly_credits_granted=row["monthly_credits_granted"],
            monthly_credits_used=row["monthly_credits_used"],
            topup_credits_balance=row["topup_credits_balance"],
            external_subscription_id=row.get("external_subscription_id"),
            last_credit_reset=row.get("last_credit_reset"),
        )

    async def process_due_subscriptions(self) -> int:
        """Expire, renew, or refresh monthly credits for due subscriptions."""
        period_rows = await self._db.fetch_all(
            """
            SELECT
                id, user_id, plan_id, status, billing_cycle,
                current_period_start, current_period_end, cancel_at_period_end,
                monthly_credits_granted, monthly_credits_used,
                topup_credits_balance, external_subscription_id,
                last_credit_reset
            FROM web_subscriptions
            WHERE status = 'active'
              AND current_period_end <= NOW()
            """
        )
        yearly_rows = await self._db.fetch_all(
            """
            SELECT
                id, user_id, plan_id, status, billing_cycle,
                current_period_start, current_period_end, cancel_at_period_end,
                monthly_credits_granted, monthly_credits_used,
                topup_credits_balance, external_subscription_id,
                last_credit_reset
            FROM web_subscriptions
            WHERE status = 'active'
              AND billing_cycle = 'yearly'
              AND current_period_end > NOW()
              AND last_credit_reset + ($1 * INTERVAL '1 day') <= NOW()
            """,
            MONTHLY_CREDIT_RESET_DAYS,
        )

        expired = 0
        handled = 0
        seen: set[str] = set()
        # Ended periods now expire (CutLuy is one-time — no silent renewal), so
        # count them for observability rather than reporting 0.
        for row in period_rows or []:
            subscription_id = str(row["id"])
            if subscription_id in seen:
                continue
            seen.add(subscription_id)
            await self.reset_quota_if_needed(self._subscription_from_row(row))
            expired += 1
        # Yearly mid-term monthly-credit refreshes.
        for row in yearly_rows or []:
            subscription_id = str(row["id"])
            if subscription_id in seen:
                continue
            seen.add(subscription_id)
            if await self.reset_quota_if_needed(self._subscription_from_row(row)):
                handled += 1
        if expired or handled:
            logger.info(
                "Web music subscription maintenance: expired=%s refreshed=%s",
                expired,
                handled,
            )
        return expired + handled

    # ─── Webhook Handling ───────────────────────────────────────────────
    
    async def handle_cutluy_webhook(
        self,
        event_type: str,
        payload: dict,
        signature: str | None,
        raw_body: bytes,
    ) -> dict:
        """Verify and process a CutLuy webhook event."""
        verified = await self._cutluy.verify_webhook_signature_async(
            raw_body,
            signature or "",
            db=self._db,
        )
        if not verified:
            logger.error("CutLuy webhook signature verification failed")
            return {"processed": False, "message": "Invalid webhook signature"}

        event = {
            "type": event_type,
            "data": payload.get("data", payload),
        }
        processed = await self._handle_webhook_event(event)
        return {
            "processed": processed,
            "message": "Subscription webhook processed" if processed else "Webhook not processed",
        }

    async def _handle_webhook_event(self, event: dict) -> bool:
        """Handle CutLuy webhook event payload."""
        event_type = event.get("type")
        data = event.get("data", {})
        
        logger.info(f"Processing CutLuy webhook: {event_type}")
        
        try:
            if event_type == "payment.completed":
                await self._handle_payment_completed(data)
            
            elif event_type == "subscription.renewed":
                await self._handle_subscription_renewed(data)
            
            elif event_type == "subscription.cancelled":
                await self._handle_subscription_cancelled(data)
            
            elif event_type == "payment.failed":
                await self._handle_payment_failed(data)
            
            else:
                logger.warning(f"Unknown webhook event type: {event_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return False
    
    async def _handle_payment_completed(self, data: dict):
        """Handle payment.completed webhook.

        Bind only to the current CutLuy payment id stored on the pending row.
        Metadata subscription_id alone must not activate a swapped plan.
        """
        try:
            payment_id = validate_payment_id(str(data.get("id") or data.get("payment_id") or ""))
        except ValueError:
            logger.error("CutLuy webhook missing a valid payment id")
            return

        row = await self._db.fetch_one(
            """
            SELECT ws.id, ws.user_id, ws.status, p.price_cents
            FROM web_subscriptions ws
            JOIN plans p ON ws.plan_id = p.id
            WHERE ws.external_subscription_id = $1
            """,
            payment_id,
        )
        if not row:
            # Renewal checkout: bound by pending_renewal_payment_id, not external.
            renewal = await self._db.fetch_one(
                """
                SELECT ws.id, ws.user_id, ws.plan_id, ws.billing_cycle,
                       ws.current_period_end, p.price_cents
                FROM web_subscriptions ws
                JOIN plans p ON ws.plan_id = p.id
                WHERE ws.pending_renewal_payment_id = $1
                """,
                payment_id,
            )
            if not renewal:
                logger.warning("No subscription bound to CutLuy payment %s", payment_id)
                return
            if not webhook_user_matches(str(renewal["user_id"]), data):
                logger.error("CutLuy renewal webhook user mismatch for payment %s", payment_id)
                return
            if not paid_amount_matches(int(renewal["price_cents"] or 0), data):
                logger.error("CutLuy renewal webhook amount mismatch for payment %s", payment_id)
                return
            await self._fulfill_renewal(renewal, payment_id)
            return
        if not webhook_user_matches(str(row["user_id"]), data):
            logger.error("CutLuy webhook user mismatch for payment %s", payment_id)
            return
        if not paid_amount_matches(int(row["price_cents"] or 0), data):
            logger.error("CutLuy webhook amount mismatch for payment %s", payment_id)
            return

        await self._fulfill_subscription_payment(
            payment_id=payment_id,
            subscription_id=str(row["id"]),
        )
    
    async def _handle_subscription_renewed(self, data: dict):
        """Handle subscription.renewed webhook."""
        external_id = data.get("subscription_id")
        
        subscription = await self._db.fetch_one("""
            SELECT id, user_id, plan_id
            FROM web_subscriptions
            WHERE external_subscription_id = $1
        """, external_id)
        
        if not subscription:
            logger.error(f"Subscription not found: {external_id}")
            return
        
        # Update last payment
        await self._db.execute("""
            UPDATE web_subscriptions
            SET last_payment_at = NOW()
            WHERE id = $1
        """, subscription["id"])
        
        # Reset will happen automatically via reset_quota_if_needed
        logger.info(f"Subscription {subscription['id']} renewed")
    
    async def _handle_subscription_cancelled(self, data: dict):
        """Handle subscription.cancelled webhook."""
        external_id = data.get("subscription_id")
        
        await self._db.execute("""
            UPDATE web_subscriptions
            SET status = 'cancelled',
                cancel_at_period_end = false
            WHERE external_subscription_id = $1
        """, external_id)
        
        logger.info(f"Subscription cancelled: {external_id}")
    
    async def _handle_payment_failed(self, data: dict):
        """Handle payment.failed webhook."""
        try:
            payment_id = validate_payment_id(
                str(data.get("id") or data.get("payment_id") or data.get("subscription_id") or "")
            )
        except ValueError:
            logger.error("CutLuy failed webhook missing a valid payment id")
            return

        await self._db.execute(
            """
            UPDATE web_subscriptions
            SET status = 'past_due'
            WHERE external_subscription_id = $1
              AND status = 'pending'
            """,
            payment_id,
        )
        
        logger.warning("Payment failed for subscription payment %s", payment_id)


# Singleton (will be replaced by dependency injection)
_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service(db) -> SubscriptionService:
    """Get SubscriptionService instance.
    
    Use in FastAPI dependencies:
        subscription_service: SubscriptionService = Depends(get_subscription_service)
    """
    return SubscriptionService(db)
