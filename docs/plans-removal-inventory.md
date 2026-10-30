# Plan removal inventory

**Companion to:** `docs/credits-only-two-tier.md`
**Goal:** delete every plan / subscription / quota / add-on code path and table, without losing
payment history, DistroKid entitlements, or user credits.

---

## 1. Database

### 1.1 Tables to archive, then drop

| Table | Rows (prod) | Archive |
|---|---:|---|
| `plans` | 22 | `plans_archive` |
| `licenses` | — | `licenses_archive` |
| `plan_offers` | 0 | `plan_offers_archive` |
| `plan_usage` | 16 | `plan_usage_archive` |
| `web_subscriptions` | 31 | `web_subscriptions_archive` |
| `user_period_quota_topups` | 3 | `user_period_quota_topups_archive` |
| `daily_quota_bank` | 26,074 | `daily_quota_bank_archive` |

### 1.2 Foreign keys that must be dropped first

| Child | Column | Parent | Delete rule | Action |
|---|---|---|---|---|
| `billing_payments` | `plan_id` | `plans` | **CASCADE** | Drop column **before** dropping `plans`, otherwise payment history is deleted. |
| `billing_payments` | `offer_id` | `plan_offers` | SET NULL | Drop column. |
| `billing_conversion_runs` | `plan_id` | `plans` | SET NULL | Drop column. |
| `licenses` | `plan_id`, `pending_plan_id` | `plans` | NO ACTION | Dropped with `licenses`. |
| `plan_offers` | `plan_id` | `plans` | NO ACTION | Dropped with `plan_offers`. |
| `plan_usage` | `license_id` | `licenses` | NO ACTION | Dropped with `plan_usage`. |
| `redeem_codes` | `applicable_plan_id` | `plans` | SET NULL | Drop column (or repurpose to credits). |
| `redeem_code_redemptions` | `plan_id` | `plans` | SET NULL | Drop column. |
| `topup_purchases` | `web_subscription_id` | `web_subscriptions` | NO ACTION | Drop column. |
| `user_period_quota_topups` | `license_id` | `licenses` | SET NULL | Dropped with the table. |
| `web_subscriptions` | `plan_id` | `plans` | NO ACTION | Dropped with `web_subscriptions`. |

### 1.3 Data that must be preserved before the drop

- `licenses.distrokid_enabled`, `licenses.distrokid_expires_at` → copy to new `users.distrokid_enabled`, `users.distrokid_expires_at` (or a dedicated table).
- `credit_wallets.balance` → authoritative; do not derive from plan lots.
- `topup_purchases` → keep entirely (it is the Pro history).
- `credit_transactions` → keep entirely.

### 1.4 Cutover data changes

1. Build the legacy set: active licenses ∪ active web subscriptions ∪ `quota_conversion` lots → **8 unique users**.
2. For each, create **one `pack` lot equal to the current wallet balance**, `expires_at = max(source expiry, now + 30d)`, `ref_id='legacy_conversion_2026_10_30'`.
3. Zero every other lot for those users (prevents double-counting the old grant/quota_conversion/pack rows).
4. For users with an existing live pack lot (not in the legacy set): keep one pack lot equal to the wallet balance.
5. For everyone else: keep one `grant` lot equal to the wallet balance (the 50 signup credits), no expiry.
6. Rebuild guarantees `balance == SUM(live lots)` for all 237 wallets.
7. Revoke licenses / cancel web subscriptions **after** archiving.
8. Copy `licenses.distrokid_*` to `users.distrokid_*` **before** dropping `licenses`.

**Expiry rule for converted lots:** because they carry `ref_id='legacy_conversion_2026_10_30'`,
the expiry sweep must move any remainder to a non-expiring `legacy` lot instead of zeroing it.
That is how the 8 users "keep their credit" after Pro lapses.

---

## 2. Backend (`platform_api/`)

### 2.1 Routers to delete

| File | Reason |
|---|---|
| `routers/plans.py` | Plan CRUD + offers. |
| `routers/licenses.py` | License CRUD + profile add-on slots. |
| `routers/v2_subscriptions.py` | Plan subscriptions. |
| `routers/web_music_plans_admin.py` | Web music plan admin. |

### 2.2 Routers to trim (not delete)

| File | Keep | Remove |
|---|---|---|
| `routers/billing.py` | Credit-pack checkout / fulfillment | Plan checkout, plan change, renewals, `_fulfill_profile_addon_payment`, `_create_profile_addon_payment_response`, `_resolve_billing_anchor_plan_id`, plan offers. |
| `routers/v3_billing.py` | Wallet/quote/pricing | `plan_id` handling, `/admin/plans/*`. |
| `routers/credits.py` | Wallet, packs, transactions | Plan/add-on daily-limit lookups (L628–636). |
| `routers/users.py` | User CRUD, wallet | `plan_name`, `license_*`, quota snapshot, `music_credits_*`, add-on fields. |
| `routers/admin.py` | User list, payments | `plan_id` filter (L1147–1193), `active_licenses` (L2070–2129). |
| `routers/stats.py` | Credits + generation counts | `licenses JOIN plans` quota fallbacks (L271–308), quota meters. |
| `routers/redeem_codes.py` | Credit redeem codes | `applicable_plan_id` preview/create (L251–286). |

### 2.3 Services to delete

- `services/v2/subscription_service.py`
- `services/v2/credit_service.py` (plan-grant paths)
- `services/v2/topup_service.py` (if plan-bound)
- `services/plan_change_service.py`
- `services/quota_topup_service.py`
- `services/quota_display_service.py`
- `services/renewal_reminder_service.py`
- `services/v3/period_grant_service.py`
- `services/subscription_entitlement_service.py` (add-on half)
- `services/license_service.py`
- `services/billing_period_service.py` (only if unused after)

### 2.4 Services to rewrite

| File | Change |
|---|---|
| `services/usage_enforcement_service.py` | Delete `_enforce_plan_quotas`, `_enforce_batch_daily_quotas`, `_subscription_covers_operation`, `_is_wallet_daily_overage`, `_record_plan_allowance_ledger`, `_sync_plan_usage_reporting`. Keep the v3 charge + fail-absorb. |
| `services/v3/credits_only_billing_service.py` | Remove `resolve_charge_plan`, `plan_id`; quote from `pricing` only. |
| `services/v3/store.py` | Remove `get_plan_for_user`, `get_plan_for_web_subscription`, `get_active_free_plan`, plan selects. |
| `services/v3/wallet_sync.py` | Remove `ensure_period_grant`; keep pack expiry + balance sync. |
| `services/web_music_service.py` | `_has_pro` → pack entitlement; remove `_has_web_subscription` plan checks. |
| `services/content_license_service.py` | Remove `web_subscriptions`/`licenses` access checks. |
| `services/onboarding_entitlement_service.py` | Remove plan-based onboarding. |

### 2.5 Repositories

- `repositories/license_repo.py` — delete `PlanRepository`; keep nothing.
- `repositories/user_repo.py` — remove `plan_name`/`is_free` filters (L368–403); add `tier` filter.
- `repositories/quota_topup_repo.py`, `repositories/daily_quota_bank_repo.py` — delete.
- `repositories/credit_repo.py` — keep packs; remove plan-linked grants.

### 2.6 Models / schemas / config

- `models/domain.py` — remove `Plan`, `License`, plan fields.
- `models/schemas.py` — remove `plan_id`, `license_*`, `music_credits_*`, add-on fields.
- `config.py` — remove `plan_monthly_overage_allowed`.
- `system_settings` — remove `plan_term_discounts`.
- `main.py` — unregister the deleted routers.

---

## 3. Admin portal (`admin_portal/`)

- Delete `src/pages/plans/` (all files) and `src/pages/licenses/`.
- Delete hooks: `use-plans`, `use-licenses`, plan/add-on mutations in `use-users`.
- User detail (`src/pages/users/user-detail.tsx`): remove Plan card (L592–611), quota table (L646–708), quota top-up dialog, add-on fields.
- User list: replace plan filter with **Tier** filter (`All / Free / Pro`), computed from live pack lots.
- Sidebar: remove Plans and Licenses entries.
- Add a **Customers** view: Pro users, last purchase, credits left, expiry.

---

## 4. Web (`camxora.com/`)

- `app/(site)/pricing/page.tsx` → replace plan cards with **credit packs** only.
- Remove upgrade/renew/subscribe CTAs and plan comparison tables.
- Any `lib/*-api.ts` helper calling `/billing/plans`, `/licenses`, `/subscriptions` → remove.
- Dashboard/account: replace plan card + quota meters with **Tier + credits + expiry**.
- Keep the pack checkout and the "Buy credits" flow.

---

## 5. Desktop (`camxora_python/`)

- `features/account/views/upgrade_plans_dialog.py` → rename to `buy_credits_dialog.py`, packs only.
- `features/account/views/auth_view.py` → gate message "Buy a credit pack to unlock".
- Dashboard: remove Plan card, `RemainingMonthCard` quota rows (credits only), `format_plan_display_name`.
- Create screen: remove plan quota labels (already credits-only).
- Settings/account: remove plan and add-on sections.
- `shared/models/platform.py`, `shared/models/auth.py`: remove plan/license fields.
- `shared/services/platform_api.py`: remove plan/license calls.

---

## 6. musicapi (`musicapi/`)

- `web-admin` / `web-user`: remove any plan/credit-plan display that maps to platform plans.
- Keep pack credits; ensure generation still debits platform credits.

---

## 7. Tests to add / update

- `platform_api/tests/test_tier_gate.py` — Free blocked, Pro allowed, expired pack → Free.
- `platform_api/tests/test_pack_expiry_tier.py` — expiry sweep flips Pro → Free.
- `platform_api/tests/test_wallet_lot_invariant.py` — `balance == SUM(live lots)` after spend/refund/expiry.
- Update/remove: `test_plan_quota_hard_cap.py`, `test_quota_display_service.py`, `test_quota_topup_service.py`, `test_users_router.py` (plan fields), `test_v3_credits_only.py` (plan mocks).

---

## 8. PR order

| PR | Scope | Risk |
|---|---|---|
| **1** | Migration (archive, convert 4 users, DistroKid copy, drop FKs/tables) + `tier_service` + `require_product_access` + `has_paid_desktop_access` rewrite | Medium — data |
| **2** | Delete plan routers/services/repos; trim billing/credits/users/stats; unregister routes | Medium — compile |
| **3** | Admin + web + desktop UI removal; tier filters; buy-credits flow | Low — UI |
| **4** | Tests, docs, dead settings, `credit_packs` cleanup | Low |

Each PR must pass `platform_api` tests and `admin_portal` build before merge.

---

## 9. Verification (post-migration)

```sql
-- every wallet equals its live lots
SELECT count(*) FROM credit_wallets w
WHERE w.balance <> COALESCE((
  SELECT SUM(remaining_units) FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id
    AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
), 0);

-- tier split
SELECT CASE WHEN EXISTS (
  SELECT 1 FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.tag='pack'
    AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
) THEN 'pro' ELSE 'free' END AS tier, count(*)
FROM credit_wallets w GROUP BY 1;

-- no plan tables left
SELECT table_name FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN ('plans','licenses','plan_usage','plan_offers','web_subscriptions');
```
