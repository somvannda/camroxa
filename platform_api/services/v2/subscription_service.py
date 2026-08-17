"""Subscription service for web music plans."""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from platform_api.services.shared.cutluy_service import CutLuyService, get_cutluy_service

logger = logging.getLogger(__name__)

# Monthly credit allowance refreshes every 30 days even on yearly billing plans.
MONTHLY_CREDIT_RESET_DAYS = 30


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


def _row_to_plan(row: dict) -> Plan:
    data = dict(row)
    data["id"] = str(data["id"])
    data["features"] = _parse_features(data.get("features"))
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
                monthly_credits, monthly_song_limit AS monthly_song_quota, features, 
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
                monthly_credits, monthly_song_limit AS monthly_song_quota, features,
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
                monthly_credits, monthly_song_limit AS monthly_song_quota, features,
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
                p.name AS plan_name
            FROM web_subscriptions ws
            JOIN plans p ON ws.plan_id = p.id
            WHERE ws.user_id = $1
              AND ws.status = 'active'
              AND (ws.cancel_at_period_end = false OR ws.current_period_end > NOW())
            ORDER BY ws.created_at DESC
            LIMIT 1
        """, user_id)

        if not row:
            return None

        subscription = Subscription(
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

        await self.reset_quota_if_needed(subscription)

        refreshed = await self._db.fetch_one("""
            SELECT 
                ws.id, ws.user_id, ws.plan_id, ws.status, ws.billing_cycle,
                ws.current_period_start, ws.current_period_end, ws.cancel_at_period_end,
                ws.monthly_credits_granted, ws.monthly_credits_used,
                ws.topup_credits_balance, ws.external_subscription_id,
                ws.created_at, ws.cancelled_at,
                p.name AS plan_name
            FROM web_subscriptions ws
            JOIN plans p ON ws.plan_id = p.id
            WHERE ws.id = $1
        """, subscription.id)

        if not refreshed:
            return None

        monthly_remaining = max(
            0,
            refreshed["monthly_credits_granted"] - refreshed["monthly_credits_used"],
        )
        result = dict(refreshed)
        result["total_credits_available"] = monthly_remaining + refreshed["topup_credits_balance"]
        return result
    
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
        # Check if user already has subscription
        existing = await self.get_user_subscription(user_id)
        if existing and existing.get("status") == "active":
            raise ValueError("User already has an active subscription")

        # Get plan
        plan = await self.get_plan_by_name(plan_name)
        if not plan:
            raise ValueError(f"Plan not found: {plan_name}")

        # Validate billing cycle matches plan
        expected_cycle = "yearly" if plan.billing_cycle_days >= 365 else "monthly"
        if billing_cycle != expected_cycle:
            raise ValueError(
                f"Plan {plan_name} requires {expected_cycle} billing cycle"
            )

        # Calculate period dates
        period_start = datetime.utcnow()
        period_end = period_start + timedelta(days=plan.billing_cycle_days)

        if existing and existing.get("status") == "pending":
            subscription_id = str(existing["id"])
            await self._db.execute(
                """
                UPDATE web_subscriptions
                SET plan_id = $1,
                    billing_cycle = $2,
                    current_period_start = $3,
                    current_period_end = $4,
                    monthly_credits_granted = $5,
                    monthly_credits_used = 0,
                    external_subscription_id = NULL,
                    updated_at = NOW()
                WHERE id = $6 AND user_id = $7 AND status = 'pending'
                """,
                plan.id,
                billing_cycle,
                period_start,
                period_end,
                plan.monthly_credits,
                subscription_id,
                user_id,
            )
        else:
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

        billing_cycle = "yearly" if plan.billing_cycle_days >= 365 else "monthly"
        return await self.create_subscription(
            user_id=user_id,
            plan_name=plan.name,
            billing_cycle=billing_cycle,
            success_url=success_url,
            cancel_url=cancel_url,
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
        logger.info(
            "Reset monthly allowance for yearly subscription %s at %s",
            subscription.id,
            reset_at.isoformat(),
        )
        return True

    async def reset_quota_if_needed(self, subscription: Subscription) -> bool:
        """Reset monthly credits when billing period or monthly allowance is due."""
        if subscription.status != "active":
            return False

        now = datetime.utcnow()
        last_reset = subscription.last_credit_reset or subscription.current_period_start

        if subscription.current_period_end <= now:
            if subscription.cancel_at_period_end:
                await self._db.execute(
                    """
                    UPDATE web_subscriptions
                    SET status = 'expired'
                    WHERE id = $1
                    """,
                    subscription.id,
                )
                logger.info("Subscription %s expired", subscription.id)
                return False

            plan = await self.get_plan_by_id(subscription.plan_id)
            if not plan:
                logger.error("Plan not found for subscription %s", subscription.id)
                return False

            next_period_start = subscription.current_period_end
            next_period_end = next_period_start + timedelta(days=plan.billing_cycle_days)

            await self._db.execute(
                """
                UPDATE web_subscriptions
                SET monthly_credits_used = 0,
                    current_period_start = $1,
                    current_period_end = $2,
                    last_credit_reset = $1
                WHERE id = $3
                """,
                next_period_start,
                next_period_end,
                subscription.id,
            )
            await self._log_monthly_credit_reset(
                user_id=subscription.user_id,
                subscription_id=subscription.id,
                monthly_credits=plan.monthly_credits,
            )
            logger.info(
                "Renewed billing period for subscription %s: %s credits",
                subscription.id,
                plan.monthly_credits,
            )
            return True

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

        handled = 0
        seen: set[str] = set()
        for row in (period_rows or []) + (yearly_rows or []):
            subscription_id = str(row["id"])
            if subscription_id in seen:
                continue
            seen.add(subscription_id)
            if await self.reset_quota_if_needed(self._subscription_from_row(row)):
                handled += 1
        if handled:
            logger.info("Processed %s due web music subscription(s)", handled)
        return handled

    # ─── Webhook Handling ───────────────────────────────────────────────
    
    async def handle_cutluy_webhook(
        self,
        event_type: str,
        payload: dict,
        signature: str | None,
        raw_body: bytes,
    ) -> dict:
        """Verify and process a CutLuy webhook event."""
        if not self._cutluy.verify_webhook_signature(raw_body, signature or ""):
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
        """Handle payment.completed webhook."""
        payment_id = data.get("id")
        subscription_id = data.get("metadata", {}).get("subscription_id")
        
        if not subscription_id:
            logger.error("No subscription_id in payment metadata")
            return
        
        # Activate subscription
        await self._db.execute("""
            UPDATE web_subscriptions
            SET status = 'active',
                external_subscription_id = $1,
                last_payment_at = NOW()
            WHERE id = $2
        """, payment_id, subscription_id)
        
        # Get subscription and plan details
        subscription = await self._db.fetch_one("""
            SELECT ws.*, p.name as plan_name, u.email
            FROM web_subscriptions ws
            JOIN plans p ON ws.plan_id = p.id
            JOIN users u ON ws.user_id = u.id
            WHERE ws.id = $1
        """, subscription_id)
        
        # TODO: Send confirmation email using existing email_service.py
        # from platform_api.services.email_service import send_verification_email
        
        logger.info(f"Activated subscription {subscription_id}")
    
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
        external_id = data.get("subscription_id")
        
        await self._db.execute("""
            UPDATE web_subscriptions
            SET status = 'past_due'
            WHERE external_subscription_id = $1
        """, external_id)
        
        logger.warning(f"Payment failed for subscription: {external_id}")


# Singleton (will be replaced by dependency injection)
_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service(db) -> SubscriptionService:
    """Get SubscriptionService instance.
    
    Use in FastAPI dependencies:
        subscription_service: SubscriptionService = Depends(get_subscription_service)
    """
    return SubscriptionService(db)
