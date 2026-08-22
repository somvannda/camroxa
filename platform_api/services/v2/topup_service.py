"""Top-up service for credit pack purchases."""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

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
from platform_api.services.v2.credit_service import CreditService, get_credit_service

logger = logging.getLogger(__name__)


@dataclass
class CreditPack:
    """Credit pack model."""
    id: str
    slug: str
    name: str
    pack_type: str
    total_credits: int
    price_cents: int
    display_order: int
    is_active: bool


@dataclass
class TopupPurchase:
    """Top-up purchase model."""
    id: str
    user_id: str
    credit_pack_id: str
    credits_purchased: int
    amount_paid_cents: int
    payment_status: str
    external_payment_id: Optional[str]
    created_at: str
    pack_name: str = ""


class TopupService:
    """Service for managing credit top-up purchases.
    
    Handles:
    - Credit pack queries
    - Top-up purchase flow
    - CutLuy payment integration
    - Webhook processing
    """
    
    def __init__(
        self,
        db,
        cutluy: Optional[CutLuyService] = None,
        credit_service: Optional[CreditService] = None
    ):
        self._db = db
        self._cutluy = cutluy or get_cutluy_service()
        self._credit_service = credit_service
    
    # ─── Pack Management ────────────────────────────────────────────────
    
    async def get_credit_packs(
        self,
        pack_type: str = "web_music",
        is_active: bool = True
    ) -> list[CreditPack]:
        """Get available credit packs.
        
        Args:
            pack_type: 'web_music' or 'desktop'
            is_active: Filter by active status
        
        Returns:
            List of credit packs
        """
        query = """
            SELECT 
                id, slug, name, pack_type, total_credits,
                price_cents, display_order, is_active
            FROM credit_packs
            WHERE pack_type = $1
        """
        params = [pack_type]
        
        if is_active:
            query += " AND is_active = true"
        
        query += " ORDER BY display_order, price_cents"
        
        rows = await self._db.fetch_all(query, *params)
        return [CreditPack(**dict(row)) for row in rows]
    
    async def get_pack_by_slug(self, slug: str) -> Optional[CreditPack]:
        """Get credit pack by slug.
        
        Args:
            slug: Pack slug (e.g., 'medium')
        
        Returns:
            CreditPack or None
        """
        row = await self._db.fetch_one("""
            SELECT 
                id, slug, name, pack_type, total_credits,
                price_cents, display_order, is_active
            FROM credit_packs
            WHERE slug = $1
              AND is_active = true
              AND pack_type = 'web_music'
        """, slug)
        
        return CreditPack(**dict(row)) if row else None
    
    async def get_pack_by_id(self, pack_id: str) -> Optional[CreditPack]:
        """Get credit pack by ID."""
        row = await self._db.fetch_one("""
            SELECT 
                id, slug, name, pack_type, total_credits,
                price_cents, display_order, is_active
            FROM credit_packs
            WHERE id = $1
        """, pack_id)
        
        return CreditPack(**dict(row)) if row else None
    
    # ─── Purchase Flow ──────────────────────────────────────────────────
    
    async def purchase_topup(
        self,
        user_id: str,
        pack_slug: str,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """Initiate top-up purchase.
        
        Args:
            user_id: User UUID
            pack_slug: Pack slug (e.g., 'medium')
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
        
        Returns:
            {
                "checkout_url": "https://cutluy.com/checkout/...",
                "payment_id": "pay_...",
                "expires_at": "..."
            }
        
        Raises:
            ValueError: If pack not found or user has no subscription
        """
        # Get pack
        pack = await self.get_pack_by_slug(pack_slug)
        if not pack:
            raise ValueError(f"Pack not found: {pack_slug}")
        if pack.pack_type != "web_music" or int(pack.price_cents or 0) < 1:
            raise ValueError("Credit pack is not available for purchase")
        success_url = sanitize_music_web_return_url(success_url)
        cancel_url = sanitize_music_web_return_url(cancel_url)

        await self._db.execute(
            """
            UPDATE topup_purchases
            SET payment_status = 'failed'
            WHERE user_id = $1
              AND payment_status = 'pending'
              AND (external_payment_id IS NULL OR external_payment_id = '')
              AND created_at < NOW() - INTERVAL '2 minutes'
            """,
            user_id,
        )
        pending_count = await self._db.fetch_val(
            """
            SELECT COUNT(*)::int
            FROM topup_purchases
            WHERE user_id = $1
              AND payment_status = 'pending'
              AND created_at > NOW() - INTERVAL '1 hour'
            """,
            user_id,
        )
        if int(pending_count or 0) >= 5:
            raise ValueError(
                "Too many pending top-up checkouts. Complete or wait for one to expire."
            )
        
        # Check if user has active subscription
        subscription = await self._db.fetch_one("""
            SELECT id
            FROM web_subscriptions
            WHERE user_id = $1 AND status = 'active'
        """, user_id)
        
        if not subscription:
            raise ValueError("User must have active subscription to purchase top-ups")
        
        # Create pending top-up purchase
        topup_id = await self._db.fetch_val("""
            INSERT INTO topup_purchases (
                user_id, web_subscription_id, credit_pack_id,
                credits_purchased, amount_paid_cents,
                payment_status
            ) VALUES (
                $1, $2, $3, $4, $5, 'pending'
            )
            RETURNING id
        """, 
            user_id, subscription["id"], pack.id,
            pack.total_credits, pack.price_cents
        )
        
        # Create CutLuy payment
        try:
            payment = await self._cutluy.create_topup_payment(
                user_id=user_id,
                pack_name=pack.name,
                amount_cents=pack.price_cents,
                credits=pack.total_credits,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "type": "topup",
                    "topup_id": str(topup_id),
                    "pack_id": str(pack.id),
                    "credits": pack.total_credits,
                },
                db=self._db,
            )
        except Exception:
            await self._db.execute(
                """
                UPDATE topup_purchases
                SET payment_status = 'failed'
                WHERE id = $1
                  AND payment_status = 'pending'
                  AND (external_payment_id IS NULL OR external_payment_id = '')
                """,
                topup_id,
            )
            raise
        
        # Store external payment ID
        await self._db.execute("""
            UPDATE topup_purchases
            SET external_payment_id = $1
            WHERE id = $2
        """, payment["payment_id"], topup_id)
        
        logger.info(
            f"Created topup purchase {topup_id} for user {user_id}: "
            f"{pack.total_credits} credits for ${pack.price_cents/100}"
        )
        
        return payment

    async def get_checkout_status(self, user_id: str, payment_id: str) -> dict[str, Any]:
        """Poll CutLuy and fulfill a web-music top-up checkout for this user."""
        try:
            payment_id = validate_payment_id(payment_id)
        except ValueError as exc:
            raise LookupError("Payment not found") from exc
        row = await self._db.fetch_one(
            """
            SELECT
                tp.id, tp.payment_status, tp.credits_purchased,
                tp.amount_paid_cents, cp.name AS pack_name
            FROM topup_purchases tp
            JOIN credit_packs cp ON tp.credit_pack_id = cp.id
            WHERE tp.user_id = $1
              AND tp.external_payment_id = $2
            ORDER BY tp.created_at DESC
            LIMIT 1
            """,
            user_id,
            payment_id,
        )
        if not row:
            raise LookupError("Payment not found")

        pack_name = row["pack_name"]
        credits = int(row["credits_purchased"] or 0)
        local_status = str(row["payment_status"] or "")

        if local_status == "completed":
            return {
                "status": "paid",
                "fulfilled": True,
                "pack_name": pack_name,
                "credits": credits,
            }
        if local_status in {"failed", "refunded"}:
            return {
                "status": "failed",
                "fulfilled": False,
                "pack_name": pack_name,
                "credits": credits,
            }

        try:
            payload = await self._cutluy.get_payment_status(payment_id, db=self._db)
        except ValueError:
            logger.exception("CutLuy status check failed for top-up %s", payment_id)
            return {
                "status": "pending",
                "fulfilled": False,
                "pack_name": pack_name,
                "credits": credits,
            }

        remote = normalize_cutluy_payment_status(payload.get("status"))
        if remote == "paid":
            if not paid_amount_matches(int(row["amount_paid_cents"] or 0), payload):
                logger.error("Refusing top-up fulfill: amount mismatch for payment %s", payment_id)
                return {
                    "status": "pending",
                    "fulfilled": False,
                    "pack_name": pack_name,
                    "credits": credits,
                }
            await self._fulfill_topup_payment(str(row["id"]), payment_id=payment_id)
            return {
                "status": "paid",
                "fulfilled": True,
                "pack_name": pack_name,
                "credits": credits,
            }
        if remote == "failed":
            await self._mark_topup_terminal(str(row["id"]), "failed", payment_id=payment_id)
            return {
                "status": "failed",
                "fulfilled": False,
                "pack_name": pack_name,
                "credits": credits,
            }
        if remote == "expired":
            await self._mark_topup_terminal(str(row["id"]), "failed", payment_id=payment_id)
            return {
                "status": "expired",
                "fulfilled": False,
                "pack_name": pack_name,
                "credits": credits,
            }
        return {
            "status": "pending",
            "fulfilled": False,
            "pack_name": pack_name,
            "credits": credits,
        }

    async def _fulfill_topup_payment(self, topup_id: str, *, payment_id: str | None = None) -> None:
        """Mark a pending top-up completed so the DB trigger grants credits."""
        if payment_id:
            await self._db.execute(
                """
                UPDATE topup_purchases
                SET payment_status = 'completed',
                    completed_at = NOW()
                WHERE id = $1
                  AND payment_status = 'pending'
                  AND external_payment_id = $2
                """,
                topup_id,
                payment_id,
            )
        else:
            await self._db.execute(
                """
                UPDATE topup_purchases
                SET payment_status = 'completed',
                    completed_at = NOW()
                WHERE id = $1
                  AND payment_status = 'pending'
                """,
                topup_id,
            )
        logger.info("Completed top-up %s", topup_id)

    async def _mark_topup_terminal(
        self,
        topup_id: str,
        status: str,
        *,
        payment_id: str | None = None,
    ) -> None:
        if payment_id:
            await self._db.execute(
                """
                UPDATE topup_purchases
                SET payment_status = $2
                WHERE id = $1
                  AND payment_status = 'pending'
                  AND external_payment_id = $3
                """,
                topup_id,
                status,
                payment_id,
            )
            return
        await self._db.execute(
            """
            UPDATE topup_purchases
            SET payment_status = $2
            WHERE id = $1
              AND payment_status = 'pending'
            """,
            topup_id,
            status,
        )
    
    # ─── Webhook Handling ───────────────────────────────────────────────
    
    async def handle_topup_webhook(
        self,
        event_type: str,
        payload: dict,
        signature: str | None,
        raw_body: bytes,
    ) -> dict:
        """Verify and process a CutLuy top-up webhook event."""
        verified = await self._cutluy.verify_webhook_signature_async(
            raw_body,
            signature or "",
            db=self._db,
        )
        if not verified:
            logger.error("CutLuy topup webhook signature verification failed")
            return {"processed": False, "message": "Invalid webhook signature"}

        event = {
            "type": event_type,
            "data": payload.get("data", payload),
        }
        processed = await self._handle_topup_event(event)
        return {
            "processed": processed,
            "message": "Top-up webhook processed" if processed else "Top-up webhook not processed",
        }

    async def _handle_topup_event(self, event: dict) -> bool:
        """Handle CutLuy webhook for top-up purchases."""
        event_type = event.get("type")
        data = event.get("data", {})
        
        logger.info(f"Processing topup webhook: {event_type}")
        
        try:
            if event_type == "payment.completed":
                await self._handle_topup_completed(data)
                return True
            
            elif event_type == "payment.failed":
                await self._handle_topup_failed(data)
                return True
            
            else:
                logger.warning(f"Unhandled topup webhook type: {event_type}")
                return False
                
        except Exception as e:
            logger.error(f"Topup webhook processing failed: {e}")
            return False
    
    async def _handle_topup_completed(self, data: dict):
        """Handle completed top-up payment.

        Credits are granted by the trigger in migration 091_topup_purchases.py.
        Lookup is by the bound CutLuy payment id, not client-influenced metadata.
        """
        try:
            payment_id = validate_payment_id(str(data.get("id") or data.get("payment_id") or ""))
        except ValueError:
            logger.error("CutLuy top-up webhook missing a valid payment id")
            return

        topup = await self._db.fetch_one(
            """
            SELECT
                tp.id, tp.user_id, tp.credits_purchased, tp.amount_paid_cents,
                cp.name as pack_name
            FROM topup_purchases tp
            JOIN credit_packs cp ON tp.credit_pack_id = cp.id
            WHERE tp.external_payment_id = $1
            """,
            payment_id,
        )
        if not topup:
            logger.warning("No top-up bound to CutLuy payment %s", payment_id)
            return
        if not webhook_user_matches(str(topup["user_id"]), data):
            logger.error("CutLuy top-up webhook user mismatch for payment %s", payment_id)
            return
        if not paid_amount_matches(int(topup["amount_paid_cents"] or 0), data):
            logger.error("CutLuy top-up webhook amount mismatch for payment %s", payment_id)
            return

        await self._fulfill_topup_payment(str(topup["id"]), payment_id=payment_id)
        logger.info(
            "Completed topup %s: granted %s credits to user %s",
            topup["id"],
            topup["credits_purchased"],
            topup["user_id"],
        )
    
    async def _handle_topup_failed(self, data: dict):
        """Handle failed top-up payment."""
        try:
            payment_id = validate_payment_id(str(data.get("id") or data.get("payment_id") or ""))
        except ValueError:
            logger.error("CutLuy top-up failed webhook missing a valid payment id")
            return

        topup = await self._db.fetch_one(
            """
            SELECT id
            FROM topup_purchases
            WHERE external_payment_id = $1
              AND payment_status = 'pending'
            """,
            payment_id,
        )
        if not topup:
            logger.warning("No pending top-up bound to failed payment %s", payment_id)
            return

        await self._db.execute(
            """
            UPDATE topup_purchases
            SET payment_status = 'failed'
            WHERE id = $1
              AND payment_status = 'pending'
              AND external_payment_id = $2
            """,
            topup["id"],
            payment_id,
        )
        logger.warning("Top-up payment failed: %s", payment_id)
    
    # ─── Purchase History ───────────────────────────────────────────────
    
    async def get_user_topups(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[TopupPurchase]:
        """Get user's top-up purchase history.
        
        Args:
            user_id: User UUID
            limit: Max results
            offset: Pagination offset
        
        Returns:
            List of top-up purchases
        """
        rows = await self._db.fetch_all("""
            SELECT 
                tp.id, tp.user_id, tp.credit_pack_id, tp.credits_purchased,
                tp.amount_paid_cents, tp.payment_status, tp.external_payment_id,
                tp.created_at, cp.name AS pack_name
            FROM topup_purchases tp
            JOIN credit_packs cp ON tp.credit_pack_id = cp.id
            WHERE tp.user_id = $1
            ORDER BY tp.created_at DESC
            LIMIT $2 OFFSET $3
        """, user_id, limit, offset)
        
        return [TopupPurchase(**dict(row)) for row in rows]
    
    async def get_topup_by_id(self, topup_id: str) -> Optional[TopupPurchase]:
        """Get top-up purchase by ID."""
        row = await self._db.fetch_one("""
            SELECT 
                id, user_id, credit_pack_id, credits_purchased,
                amount_paid_cents, payment_status, external_payment_id,
                created_at
            FROM topup_purchases
            WHERE id = $1
        """, topup_id)
        
        return TopupPurchase(**dict(row)) if row else None
    
    # ─── Admin Operations ───────────────────────────────────────────────
    
    async def refund_topup(
        self,
        topup_id: str,
        admin_id: str,
        reason: str
    ) -> bool:
        """Refund a top-up purchase (admin only).
        
        Args:
            topup_id: Top-up purchase ID
            admin_id: Admin user ID
            reason: Refund reason
        
        Returns:
            True if refunded successfully
        """
        topup = await self.get_topup_by_id(topup_id)
        if not topup or topup.payment_status != "completed":
            return False
        
        # Update status
        await self._db.execute("""
            UPDATE topup_purchases
            SET payment_status = 'refunded',
                refunded_at = NOW()
            WHERE id = $1
        """, topup_id)
        
        # Deduct credits (if user still has them)
        if self._credit_service:
            try:
                await self._credit_service.consume_credits(
                    user_id=topup.user_id,
                    amount=topup.credits_purchased,
                    source="topup_refund",
                    reference_id=topup_id
                )
            except Exception as e:
                logger.warning(f"Could not deduct refunded credits: {e}")
        
        logger.warning(
            f"Admin {admin_id} refunded topup {topup_id}: {reason}"
        )
        
        return True


# Factory function for dependency injection
def get_topup_service(db) -> TopupService:
    """Get TopupService instance.
    
    Use in FastAPI dependencies:
        topup_service: TopupService = Depends(get_topup_service)
    """
    return TopupService(db)
