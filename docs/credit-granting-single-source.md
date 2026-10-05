# Credit granting — single source of truth (design + rollout)

**Date:** 2026-10-05
**Surfaces:** platform_api (DB `plans`, `system_settings`), admin_portal
**Status:** Phase 1 implemented; Phases 2–4 proposed

## Goal

Make it impossible for credits to be granted "from everywhere" or for a plan's
allowance to mean two different things. One **configuration** source and one
**grant** choke point, with refunds kept as a distinct, first‑class operation.

## 1. Where credits are granted today

`credit_wallets.balance` is written by many paths:

| Path | Grant | Idempotent? |
|---|---|---|
| `v3/period_grant_service.ensure_period_grant` | plan monthly allowance | lot `(user, period_start)` |
| `v3/period_grant_service.ensure_daily_grant` | plan daily allowance | lot `(user, day)` |
| `v3/period_grant_service.carryover_period_grant` | early‑renewal carryover | lot `(user, next_period)` |
| `v3/wallet_sync.after_subscription_fulfill` | period grant | via caller |
| `v3/wallet_sync.after_topup_fulfill` | top‑up pack | `v3_pack:{topup_id}` (ad‑hoc) |
| `v3/quota_conversion_service`, `v3/web_ledger_conversion` | cutover conversion | ad‑hoc |
| `billing_mode_service.grant_included_wallet_credits` | licence lifetime bonus | no |
| `routers/billing._fulfill_paid_payment` | paid plan credits | no |
| `services/credit_service` (v2) | top‑up / admin / renewal | partial |
| `services/license_service.add_credits` | licence | no |
| `repositories/credit_repo.add_credits` | the primitive | **no** |
| `redeem_code_service`, `onboarding_entitlement_service` | redeem / onboarding | raw `UPDATE credit_wallets` |
| ops scripts (clawback / reconcile) | corrections | manual |

The primitive `CreditRepository.add_credits()` accepts any `reason`, has no
idempotency key, and is bypassed by raw SQL in two services. That is why the
period‑grant bug could mint repeatedly.

## 2. Configuration inventory ("how many places")

**Authoritative (grants read these): `plans` — one table, three columns**
- `plans.monthly_credits` → `ensure_period_grant`
- `plans.daily_credits` → `ensure_daily_grant`
- `plans.included_wallet_credits` → `grant_included_wallet_credits`

**Write surfaces (4):**
1. `PATCH /api/v3/admin/plans/{id}` (`routers/v3_billing.py`) — `monthly_credits`, `daily_credits` (both `ge=0`).
2. `POST/PATCH/DELETE /api/v1/.../web-music/plans` (`routers/web_music_plans_admin.py`) — `monthly_credits` only, `ge=1`.
3. Alembic migrations (`127`, `130`, `030`) + deploy scripts.
4. Direct SQL / ops scripts.

**Competing / legacy (2):**
- `system_settings.music_web_free_reset_period` (`"daily" | "monthly"`) — still read by `services/v2/credit_service.py`.
- `system_settings.credits_only_v3_charge` — switches v2/v3 charging (overrides env `PLATFORM_CREDITS_ONLY_V3_CHARGE=false`).

**Per‑subscription record (1):** `web_subscriptions.monthly_credits_granted` (now refreshed on renewal).

## 3. Behaviour matrix (Free plan `daily=0, monthly=50`)

`resolve_charge_plan()` precedence: **licence → active paid web subscription → active Free plan**.

| account | resolves to | per period |
|---|---|---|
| Free (no licence, no active web sub) | Free | **50 / month** |
| Active paid web subscriber | their web plan | plan monthly (1,000/2,300/5,500/8,800) |
| Active **$79 desktop** licence | licence plan (5,150/mo) | **5,150 / licence period** |
| Lapsed paid account (web or desktop) | Free | **50 / month** |

`monthly_credits=50` on Free therefore affects only accounts that resolve to
Free. Active desktop $79 users keep their own allowance.

## 4. Target design

### 4.1 One config, exclusive cadence
- `plans` stays the single source. Enforce **daily XOR monthly**
  (`daily_credits > 0 XOR monthly_credits > 0`); `included_wallet_credits` is the
  separate one‑time bonus.
- Enforce at the DB (`CHECK`) **and** in the API (`validate_credit_cadence`).
- One validation helper used by **every** editor path.
- Retire `music_web_free_reset_period`; derive cadence from the resolved plan.

### 4.2 One grant choke point
`credit_wallets` becomes writable only through three typed operations:

| op | purpose | key |
|---|---|---|
| `deduct()` | spend | `ref_id` |
| `grant()` | entitlement (signup / period / daily / pack / conversion / admin / reconcile) | `(user, type, ref_id)` |
| `refund()` | reverse a specific debit | `(user, reason, ref_id)` |

Expiry + period anchoring live **inside** `grant()`. Callers pass intent only.

### 4.3 Refunds stay separate and idempotent
A refund is **not** an entitlement. It reverses a specific debit, capped at the
debited amount, keyed on `(user, reason, ref_id)` (already enforced by
`idx_credit_txn_refund_idempotency`). Failed generations keep working:
charge at submit → on failure `refund_once()` reverses the debit once. This is
unchanged by the consolidation.

## 5. Rollout

### Phase 1 — single, exclusive config ✅ (this change)
- Migration `131`: `CHECK` daily/monthly exclusivity; delete the retired
  `music_web_free_reset_period` setting.
- `services/plan_credits.py::validate_credit_cadence` used by the v3 admin PATCH
  and the web‑music plan create/update.
- `v2/credit_service.free_reset_period()` derives from the Free plan row.
- Tests.

**Acceptance:** no plan can have both daily & monthly > 0 (DB + API); one cadence
source; Free `daily=0/monthly=50` grants 50/month to Free + lapsed only.

### Phase 2 — grant choke point ✅
- ✅ `(user, reason, ref_id)` grant idempotency via a non-destructive
  `credit_grant_claims` table (migration `133`) + `add_credits(..., idempotent=)`.
- ✅ Typed `services/credit_ledger.py` facade (`CreditLedger.grant/deduct/refund`
  + `GrantType`) is the named entry point; the plan/pack/conversion/licence-bonus
  grants and `redeem_code_service` now go through it.
- `CreditRepository` remains the low-level writer. Remaining direct callers
  (`billing.py` paid-plan fulfilment, `services/v2/credit_service.py`) still call
  it and can migrate to the facade incrementally.

### Phase 3 — mint on events, not reads ✅
- `/me/credits` is now **read-only**; period/daily grants run on billing events
  (webhook/renewal) + a new single-winner **grant-maintenance scheduler**
  (startup + hourly), so balances are correct without a GET mutating them. This
  also fixes "Free monthly credits only appear when the wallet page is opened".
- The web-music charge path still mints (idempotently) so a user can generate
  immediately after granting; new accounts are covered by the scheduler tick.

### Phase 4 — detection + backstop
- Daily invariant job ("≤1 live grant lot per user per period") + anomaly alert
  (>1 period grant per user/period, abnormal daily volume).
- DB constraint/trigger requiring a ledger row for every wallet change.

## 6. Risks / tradeoffs
- Refactor breadth (Phase 2 reaches ~10 call sites); preserve licence/pack/refund
  semantics; needs sandbox verification.
- New uniqueness on grants requires confirming no historical duplicates.
- Retiring the legacy setting is a one‑way config change (downgrade re‑inserts).
