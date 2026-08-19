# Phase 1: Web Music Credit-Based Subscription System

**Date:** August 16, 2026  
**Type:** Feature - Database Foundation  
**Surfaces:** Platform API (Database)

## Summary

Implemented database foundation for Phase 1 web music subscription system with credit-based billing, extending existing infrastructure to support web-only music generation plans.

## Database Changes

### New Migrations

#### 088_web_music_subscription_plans.py
- **Extended `plans` table** with web music plan support
- Added columns:
  - `plan_type` VARCHAR(20) - Differentiates 'web_music' from 'desktop_pro'
  - `monthly_credits` INTEGER - Credit-based quota
  - `features` JSONB - Feature flags (music, images, topup)
  - `is_public` BOOLEAN - Controls pricing page visibility
  - `display_order` INTEGER - Sorting order
- **Inserted 6 new web music plans:**
  - Starter Monthly: $10/mo, 1,000 credits (100 songs)
  - Starter Yearly: $102/yr (15% off), 1,000 credits/mo
  - Creator Monthly: $30/mo, 3,500 credits (350 songs)
  - Creator Yearly: $306/yr (15% off), 3,500 credits/mo
  - Studio Monthly: $60/mo, 8,000 credits (800 songs)
  - Studio Yearly: $612/yr (15% off), 8,000 credits/mo

#### 089_web_subscriptions.py
- **Created `web_subscriptions` table** for web music subscription instances
- Columns:
  - Relations: user_id, plan_id
  - Status: status (active/cancelled/expired/past_due)
  - Billing: billing_cycle, current_period_start/end, cancel_at_period_end
  - Payment: payment_provider (cutluy), external_subscription_id, external_customer_id
  - Credits: monthly_credits_granted, monthly_credits_used, last_credit_reset
- **Unique constraint:** One subscription per user
- **Indexes:** user_id, status, period_end, external_subscription_id
- **Trigger:** auto-update updated_at timestamp

#### 090_update_credit_packs.py
- **Extended `credit_packs` table** for web music top-ups
- Added columns:
  - `slug` VARCHAR(50) - Unique identifier (e.g., 'small', 'medium')
  - `total_credits` INTEGER - Total credits in pack
  - `pack_type` VARCHAR(20) - Differentiates 'web_music' from 'desktop'
  - `display_order` INTEGER - Sorting order
- **Inserted 4 web music credit packs:**
  - Small: 400 credits, $5 (40 songs) - 52% margin
  - Medium: 1,000 credits, $10 (100 songs) - 40% margin
  - Large: 2,500 credits, $25 (250 songs) - 40% margin
  - Mega: 8,000 credits, $50 (800 songs) - 4% margin

#### 091_topup_purchases.py
- **Created `topup_purchases` table** to track credit top-up purchases
- Columns:
  - Relations: user_id, web_subscription_id, credit_pack_id
  - Purchase: credits_purchased, amount_paid_cents, currency
  - Payment: payment_provider (cutluy), external_payment_id, payment_status
  - Timestamps: created_at, completed_at, refunded_at
- **Trigger `grant_topup_credits()`:**
  - Automatically adds credits to `credit_wallets` when payment completes
  - Logs transaction to `credit_transactions`
  - Updates `topup_credits_balance` in `web_subscriptions`
- **Added to `web_subscriptions`:**
  - `topup_credits_balance` INTEGER - Permanent top-up credit balance

## Reused Existing Infrastructure

No new tables needed for:
- ✅ `credit_wallets` - User credit balances
- ✅ `credit_transactions` - Transaction audit log
- ✅ `credit_pricing` - Credits per operation
- ✅ `email_verifications` - Email verification tokens
- ✅ `users.email_confirmed` - Email confirmation status

## Backend Services & API Endpoints

### New Services

#### TurnstileService (`platform_api/services/shared/turnstile_service.py`)
- Cloudflare Turnstile bot protection
- Token verification against Cloudflare API
- Methods: `verify_token()`, `verify_or_raise()`

#### CutLuyService (`platform_api/services/shared/cutluy_service.py`)
- CutLuy payment integration (Cambodia KHQR payments)
- Creates subscription checkout sessions
- Creates one-time payment links for top-ups
- Webhook signature verification (reuses `platform_api/services/cutluy_webhook.py`)
- Methods: `create_subscription_payment()`, `create_topup_payment()`, `get_payment_status()`, `cancel_subscription()`, `verify_webhook_signature()`

#### SubscriptionService (`platform_api/services/v2/subscription_service.py`)
- Web music subscription management
- Plan listing and subscription lifecycle
- Credit quota tracking and resets
- CutLuy webhook handling for payments
- Methods: `get_plans()`, `get_user_subscription()`, `create_subscription()`, `cancel_subscription()`, `get_credit_balance()`, `reset_quota_if_needed()`, `handle_cutluy_webhook()`

#### CreditService (`platform_api/services/v2/credit_service.py`)
- Atomic credit operations with row locking
- Credit consumption and granting
- Transaction history tracking
- Methods: `get_detailed_balance()`, `get_total_balance()`, `has_sufficient_credits()`, `consume_credits()`, `grant_credits()`, `get_transaction_history()`, `manual_credit_adjustment()`

#### TopupService (`platform_api/services/v2/topup_service.py`)
- Credit top-up purchase management
- Credit pack listing
- CutLuy webhook handling for top-ups
- Methods: `get_credit_packs()`, `get_pack_by_slug()`, `purchase_topup()`, `handle_topup_webhook()`, `get_user_topups()`, `refund_topup()`

### API Endpoints (v2)

#### Subscriptions (`/api/v1/v2/subscriptions`)
- `GET /plans` - List all web music plans
- `GET /my-subscription` - Get current user's subscription
- `POST /purchase` - Create CutLuy checkout for subscription
- `POST /cancel` - Cancel subscription (immediate or at period end)

#### Credits (`/api/v1/v2/credits`)
- `GET /balance` - Get detailed credit balance (monthly + topup)
- `GET /history` - Get credit transaction history
- `POST /consume` - Consume credits (internal API for generation)

#### Top-ups (`/api/v1/v2/topups`)
- `GET /packs` - List all credit top-up packs
- `POST /purchase` - Create CutLuy checkout for top-up
- `GET /history` - Get user's top-up purchase history

#### Webhooks (`/api/v1/webhooks`)
- `POST /cutluy` - Handle CutLuy payment webhooks
  - Subscription events: `subscription.activated`, `subscription.renewed`, `subscription.cancelled`
  - Payment events: `payment.completed`, `payment.failed`
  - Signature verification with HMAC-SHA256
  - Automatic credit granting on successful payment
- `GET /cutluy/health` - Webhook health check

### Service Consolidation
- Removed duplicate `EmailService` - reuses existing `platform_api/services/email_service.py`
- Updated `CutLuyService` to use existing `verify_cutluy_webhook_signature()` from `platform_api/services/cutluy_webhook.py`
- All new services properly integrated with dependency injection via `wire_dependencies.py`

## Frontend Components (`music_web/`)

### New API Client
**`src/lib/subscription-api.ts`** - v2 API client with complete type definitions:
- Types: `SubscriptionPlan`, `UserSubscription`, `CreditBalance`, `CreditPack`, etc.
- Subscription API: `fetchSubscriptionPlans()`, `fetchMySubscription()`, `purchaseSubscription()`, `cancelSubscription()`
- Credit API: `fetchCreditBalance()`, `fetchCreditHistory()`
- Top-up API: `fetchCreditPacks()`, `purchaseTopup()`, `fetchTopupHistory()`
- Utilities: `creditsToSongs()`, `formatPrice()`, `calculateDiscount()`, `hasSufficientCredits()`

### New Pages

#### `/pricing` - Pricing Page
**Files:** `src/app/pricing/page.tsx` + `src/components/pricing-page-client.tsx`
- Beautiful 3-tier plan cards (Starter/Creator/Studio)
- Monthly vs Yearly toggle with discount badge
- Real-time plan data from API
- Direct CutLuy checkout integration
- Responsive grid layout with popular plan highlighting

#### `/profile` - Enhanced Profile Page
**File:** `src/app/profile/page.tsx` (updated)
- Integrated credit balance card
- Subscription management section
- User info display

### New Components

#### `CreditBalanceCard` (`src/components/credit-balance-card.tsx`)
- Live credit balance display with monthly vs top-up breakdown
- Songs remaining counter
- Buy more credits button
- Auto-refresh every 30 seconds

#### `SubscriptionSection` (`src/components/subscription-section.tsx`)
- Current subscription details and plan features
- Next billing date countdown
- Cancel subscription modal (immediate or at period end)
- Upgrade CTA for non-subscribers

#### `TopupModal` (`src/components/topup-modal.tsx`)
- Credit pack cards (Small/Medium/Large/Mega)
- Price and credits display with songs equivalent
- Direct CutLuy checkout integration
- Popular pack highlighting in responsive 2-column grid

#### `CreditHeader` (`src/components/credit-header.tsx`)
- Compact credit display for create page
- Low credit warning indicator
- Quick top-up button
- Real-time balance updates

### UI Features
- 🎨 Consistent purple/pink gradient theme throughout
- 🌙 Dark mode optimized (#0a0e27 → #1a1f3a gradient)
- 📱 Fully responsive design (mobile-first)
- ⚡ Real-time credit updates (auto-refresh)
- 🔒 Secure payment flow with CutLuy integration
- ✨ Smooth animations and transitions
- 🎯 Clear CTAs and user guidance

## Credit Economics

**Cost Model:**
- Suno COGS: $0.06 per song (2 versions)
- 1 credit = $0.01
- Song generation: 10 credits ($0.10)

**Profit Margins:**
- Starter ($10/mo): $4.00 profit (40%)
- Creator ($30/mo): $9.00 profit (30%)
- Studio ($60/mo): $12.00 profit (20%)
- Top-up packs: 4-52% margin

**Top-up Credit Rules:**
- Monthly credits reset at billing cycle (no rollover)
- Top-up credits never expire
- Top-up credits used after monthly credits
- Only available to paid subscribers

## Admin Portal Integration

**Plan Management:**
- Single interface for all plans (desktop + web)
- Filter by `plan_type`
- Create/edit plans with plan type selector
- All features accessible from existing admin UI

**Credit Pack Management:**
- Filter by `pack_type`
- Create/edit packs with pack type selector
- View pack analytics

## Next Steps (Phase 1 Continuation)

**Backend Services (Week 3):**
- SubscriptionService - Plan management, CutLuy webhooks
- CreditService - Credit consumption, balance tracking
- TopupService - Purchase flow, webhook handling
- EmailVerificationService - Already exists, may need updates
- TurnstileService - Cloudflare bot protection

**Web Frontend (Week 4):**
- Signup with Cloudflare Turnstile
- Email verification flow
- Pricing page
- Account page (credits + subscription)
- Top-up purchase flow
- Credit display on create page

**Admin Portal (Week 5):**
- Credit pack CRUD (extends existing)
- Subscription analytics
- Manual credit adjustment tool

## Migration Deployment

**Sandbox:**
```bash
python scripts/deploy/run_alembic_upgrade_sandbox.py
```

**Production:**
```bash
python scripts/deploy/run_alembic_upgrade_production.py
```

## Rollback

All migrations support rollback via `downgrade()`:
```bash
alembic downgrade -1  # Rollback one migration
```

## Testing Checklist

- [ ] Migrations run successfully on local dev
- [ ] Migrations run successfully on sandbox
- [ ] Web music plans visible in database
- [ ] Credit packs visible in database
- [ ] No impact on existing desktop plans/licenses
- [ ] Existing credit system continues working
- [ ] Admin portal displays all plan types

## Breaking Changes

None. All changes are additive and backward compatible.

## References

- Design Doc: `docs/PHASE_1_WEB_MUSIC_CREDITS.md`
- Cloudflare Turnstile Setup: Section 6 of design doc
- Credit Economics: Section 2 of design doc
