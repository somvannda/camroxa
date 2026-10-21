"""Top-up service for credit pack purchases."""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from uuid import UUID

from platform_api.services.shared.cutluy_service import (
    CutLuyService,
    get_cutluy_service,
    normalize_cutluy_payment_status,
)
from platform_api.services.billing_provider_service import resolve_active_provider
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

    async def _payment_provider(self) -> str:
        """Return the admin-selected KHQR provider, defaulting to CutLuy.

        The panel switch decides which gateway a *new* checkout uses; an
        in-flight purchase keeps the provider stored on its own row, so flipping
        the switch never strands a pending payment.
        """
        pool = getattr(self._db, "_pool", None)
        if pool is None:
            return "cutluy"
        try:
            provider = await resolve_active_provider(pool)
        except Exception:
            logger.exception("billing provider resolution failed; falling back to CutLuy")
            return "cutluy"
        return provider or "cutluy"
    
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
            ValueError: If pack not found or not purchasable
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
        
        # Top-up packs are the only sellable product now, so an active
        # subscription is no longer required to buy one (it used to gate this
        # checkout). When the buyer happens to be a grandfathered subscriber we
        # still link the purchase for reporting; otherwise the FK stays NULL.
        subscription = await self._db.fetch_one("""
            SELECT id
            FROM web_subscriptions
            WHERE user_id = $1 AND status = 'active'
        """, user_id)

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
            user_id, subscription["id"] if subscription else None, pack.id,
            pack.total_credits, pack.price_cents
        )
        
        # Create the gateway payment. The provider is resolved once per
        # checkout and recorded on the row so status polling/webhooks keep
        # talking to the gateway that actually holds the money.
        provider = await self._payment_provider()
        try:
            if provider == "chmaba":
                from platform_api.services.shared.chmaba_service import ChmabaService

                payment = await ChmabaService().create_payment(
                    amount_cents=int(pack.price_cents),
                    # The provider echoes `reference_id` back on every webhook,
                    # so the local top-up id is the stable handle back to this row.
                    reference_id=str(topup_id),
                    metadata={
                        "type": "topup",
                        "topup_id": str(topup_id),
                        "pack_id": str(pack.id),
                        "credits": pack.total_credits,
                        "user_id": user_id,
                    },
                    db=self._db,
                )
            else:
                provider = "cutluy"
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

        # Store the provider payment id and which gateway minted it.
        await self._db.execute("""
            UPDATE topup_purchases
            SET external_payment_id = $1,
                payment_provider = $2
            WHERE id = $3
        """, payment["payment_id"], provider, topup_id)

        logger.info(
            f"Created topup purchase {topup_id} for user {user_id} via {provider}: "
            f"{pack.total_credits} credits for ${pack.price_cents/100}"
        )

        return {**payment, "provider": provider}

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
                tp.amount_paid_cents, tp.payment_provider, cp.name AS pack_name
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
        provider = str(row.get("payment_provider") or "cutluy")

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
            if provider == "chmaba":
                from platform_api.services.shared.chmaba_service import (
                    ChmabaService,
                    normalize_chmaba_payment_status,
                )

                payload = await ChmabaService().get_payment_status(payment_id, db=self._db)
                remote = normalize_chmaba_payment_status(payload.get("status"))
            else:
                payload = await self._cutluy.get_payment_status(payment_id, db=self._db)
                remote = normalize_cutluy_payment_status(payload.get("status"))
        except Exception:
            logger.exception("%s status check failed for top-up %s", provider, payment_id)
            return {
                "status": "pending",
                "fulfilled": False,
                "pack_name": pack_name,
                "credits": credits,
            }

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
        await self._sync_v3_pack(topup_id)

    async def _sync_v3_pack(self, topup_id: str) -> None:
        row = await self._db.fetch_one(
            """
            SELECT user_id, credits_purchased
            FROM topup_purchases
            WHERE id = $1
            """,
            topup_id,
        )
        if not row or not row.get("user_id"):
            return
        from platform_api.services.v3.wallet_sync import sync_topup_pack
        from uuid import UUID

        credits = int(row.get("credits_purchased") or 0)
        result = await sync_topup_pack(
            UUID(str(row["user_id"])),
            credits,
            topup_id=str(topup_id),
        )
        if result and credits > 0:
            # Referral rewards ride after the pack mint and are idempotent: the
            # referral row is claimed once, so repeated status polls are safe.
            try:
                from platform_api.dependencies import get_db_pool
                from platform_api.services.invite_program_service import apply_referral_reward

                pool = get_db_pool()
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await apply_referral_reward(
                            conn,
                            invitee_id=UUID(str(row["user_id"])),
                            purchased_credits=credits,
                            qualifying_ref=str(topup_id),
                        )
            except Exception:
                logger.exception(
                    "invite reward failed for topup %s user=%s",
                    topup_id,
                    row.get("user_id"),
                )

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

    async def settle_chmaba_topup(self, *, event_type: str, topup_id: str) -> dict:
        """Settle a ChmabaPay event that was bound to a local top-up row.

        ChmabaPay echoes the ``reference_id`` we set at checkout (the local
        top-up id), so no client-supplied metadata is trusted here. The row's
        own pending state makes the operation idempotent across webhook
        retries and a racing status poll.
        """
        try:
            UUID(str(topup_id))
        except (TypeError, ValueError):
            return {"processed": False, "message": "Invalid top-up reference"}

        row = await self._db.fetch_one(
            """
            SELECT id, payment_status
            FROM topup_purchases
            WHERE id = $1
              AND payment_provider = 'chmaba'
            """,
            topup_id,
        )
        if not row:
            return {"processed": False, "message": "No ChmabaPay top-up for this reference"}

        if event_type == "payment.completed":
            if str(row["payment_status"]) != "pending":
                return {"processed": True, "message": "Top-up already settled"}
            await self._fulfill_topup_payment(str(row["id"]))
            return {"processed": True, "message": "Top-up credited"}

        if event_type in {"payment.reversed", "payment.failed"}:
            target = "refunded" if event_type == "payment.reversed" else "failed"
            await self._mark_topup_terminal(str(row["id"]), target)
            return {"processed": True, "message": f"Top-up marked {target}"}

        if event_type == "payment.superseded":
            # The code was replaced and can never settle; fail it so a new
            # checkout is allowed instead of waiting out the pending window.
            await self._mark_topup_terminal(str(row["id"]), "failed")
            return {"processed": True, "message": "Top-up marked failed (superseded)"}

        if event_type == "payment.expired":
            # Not terminal: a late payment still promotes the row to paid.
            return {"processed": False, "message": "Ignored expired event"}

        return {"processed": False, "message": f"Ignored event: {event_type}"}

    
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
