# Execution plan — remove plans, ship two-tier credits-only

**Branch:** `chore/credits-only-two-tier`
**Spec:** `docs/credits-only-two-tier.md` · **Inventory:** `docs/plans-removal-inventory.md`
**Migration:** `platform_api/migrations/versions/174_credits_only_two_tier.py`
**Verification:** `docs/migration-174-verification.sql`

## Current status (2026-10-30)

| Gate | Status |
|---|---|
| Plan routers removed | ✅ `/plans`, `/licenses`, `/subscriptions` unmounted |
| Hot paths plan-free | ✅ generation, billing, wallet, web music, auth, callbacks |
| `import platform_api.main` | ✅ |
| `pytest platform_api/tests` | ✅ 3,161 passed |
| Migration 174 | 🟡 dry-run in progress on `camxora_staging_174` |
| Plan tables in prod | ⬜ still present (expected) |
| Admin / web / desktop UI | ⬜ pending |

**Migration strategy change:** `billing_payments.plan_id` / `offer_id` are kept as
**nullable legacy audit columns**; only their FKs are dropped. This preserves payment
history and removes the deploy circular dependency. A follow-up migration drops them.


---

## 0. Locked decisions

| User | Credits | Tier | Until |
|---|---:|---|---|
| sophay@camxora.com | 8,658.95 | Pro | 2026-11-01 |
| mr.zhiwei@gmail.com | 5,009.85 | Pro | 2026-11-01 |
| edmbass1@gmail.com | 2,676.43 | Pro | 2026-11-03 |
| tepchanpanharith@gmail.com | 0.11 | Pro | 2026-11-06 |
| iamduke1987@gmail.com | 886.00 | Pro | 2026-11-05 |
| mr.limeang.018@gmail.com | 520.00 | Pro | 2026-11-12 |
| pich.sou11@gmail.com | 50.00 | Free | — |
| teangchunpanhavorn@gmail.com | 50.00 | Free | — |

- 5 other live pack buyers stay **Pro** until their pack expiry.
- Everyone else stays **Free** with their 50 signup credits.
- Converted pack lots use the **original expiry** — no invented dates.
- On expiry: Pro → Free, **credits are kept** in a non-expiring `legacy` lot.
- No plans, quotas, subscriptions, add-ons, or profile limits.

Expected split after migration: **11 Pro / 226 Free / 237 total**.

---

## 1. Phase 0 — Safety and freeze

**Goal:** nothing can be sold or mutated while we change the model.

| # | Task | Detail | Done when |
|---|---|---|---|
| 0.1 | Snapshot | `pg_dump -Fc camxora_platform` + copy off-box | Restore verified on staging |
| 0.2 | Record baseline | Row counts: users, wallets, lots, songs, topup_purchases, credit_transactions | Saved to `docs/migration-174-baseline.txt` |
| 0.3 | Freeze plan sales | Disable plan checkout routes (`POST /billing/checkout` plan path, `/v2/subscriptions`) | Attempt returns 410 |
| 0.4 | Freeze plan mutations | Disable `PATCH /plans/{id}`, license create/assign/revoke | Admin returns 410 |
| 0.5 | Notify | Tell the 8 users + 5 pack buyers about the change | Message sent |

**Acceptance:** no new licenses/subscriptions can be created; snapshot restores cleanly.

---

## 2. Phase 1 — Data migration (174)

**Goal:** every wallet obeys `balance == SUM(live lots)`, tiers derive correctly, plan tables gone.

### 2.1 What the migration does, in order

1. Add `users.distrokid_enabled`, `users.distrokid_expires_at`; copy from active licenses.
2. Archive `plans`, `licenses`, `plan_offers`, `plan_usage`, `web_subscriptions`,
   `user_period_quota_topups`, `daily_quota_bank`, and `credit_wallet_lots`.
3. Build `_tier_rebuild`:
   - `active_legacy` = active license ∪ active web sub → pack lot = wallet, expiry = **original**.
   - `expired_reset` = `quota_conversion` user with no active plan/sub → wallet **50**, grant lot.
   - `pack_u` = any other live pack → pack lot = wallet, expiry = original pack expiry.
   - everyone else → grant lot = wallet, no expiry.
4. Update `credit_wallets.balance` for the reset users only (pich, teangchun → 50).
5. Zero all old lots, insert one lot per user.
6. Revoke licenses, cancel web subscriptions.
7. Drop FK columns (`billing_payments.plan_id/offer_id` **first** — CASCADE).
8. Drop the 7 plan tables.
9. Delete `plan_term_discounts` setting.

### 2.2 Dry-run procedure

```bash
# staging
createdb camxora_staging
pg_restore -d camxora_staging backup.dump
cd platform_api && alembic upgrade head
```

### 2.3 Acceptance queries

```sql
-- 1. invariant: must return 0
SELECT count(*) FROM credit_wallets w
WHERE w.balance <> COALESCE((
  SELECT SUM(remaining_units) FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
), 0);

-- 2. tier split: expect 11 pro / 226 free
SELECT CASE WHEN EXISTS (
  SELECT 1 FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.tag='pack'
    AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
) THEN 'pro' ELSE 'free' END AS tier, count(*)
FROM credit_wallets w GROUP BY 1;

-- 3. converted users
SELECT u.email, round(w.balance/10000.0,2) credits,
       l.expires_at::date, l.ref_id
FROM users u
JOIN credit_wallets w ON w.user_id = u.id
JOIN credit_wallet_lots l ON l.user_id = u.id AND l.remaining_units > 0
WHERE u.email IN (
  'sophay@camxora.com','mr.zhiwei@gmail.com','edmbass1@gmail.com',
  'tepchanpanharith@gmail.com','iamduke1987@gmail.com','mr.limeang.018@gmail.com',
  'pich.sou11@gmail.com','teangchunpanhavorn@gmail.com')
ORDER BY u.email;

-- 4. plan tables gone: must return 0 rows
SELECT table_name FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN ('plans','licenses','plan_usage','plan_offers','web_subscriptions');
```

**Acceptance:** all four pass; `billing_payments` row count unchanged.

---

## 3. Phase 2 — Backend removal

**Goal:** API compiles and runs with no plan tables, packs only.

### 3.1 Delete

| File | Note |
|---|---|
| `platform_api/routers/plans.py` | plan CRUD + offers |
| `platform_api/routers/licenses.py` | licenses + add-on slots |
| `platform_api/routers/v2_subscriptions.py` | plan subscriptions |
| `platform_api/routers/web_music_plans_admin.py` | web plan admin |
| `platform_api/services/license_service.py` | |
| `platform_api/services/plan_change_service.py` | |
| `platform_api/services/quota_topup_service.py` | |
| `platform_api/services/quota_display_service.py` | |
| `platform_api/services/renewal_reminder_service.py` | |
| `platform_api/services/v2/subscription_service.py` | |
| `platform_api/services/v3/period_grant_service.py` | |
| `platform_api/services/subscription_entitlement_service.py` | add-on half |
| `platform_api/repositories/quota_topup_repo.py` | |
| `platform_api/repositories/daily_quota_bank_repo.py` | |

### 3.2 Trim

| File | Remove | Keep |
|---|---|---|
| `routers/billing.py` | plan checkout, plan change, renewals, `_fulfill_profile_addon_payment`, `_create_profile_addon_payment_response`, `_resolve_billing_anchor_plan_id` | pack checkout + fulfillment |
| `routers/v3_billing.py` | `plan_id` params, `/admin/plans/*` | quote, pricing, wallet |
| `routers/credits.py` | add-on/daily-limit lookups (L628–636) | wallet, packs, transactions |
| `routers/users.py` | `plan_name`, `license_*`, `music_credits_*`, quota snapshot, add-on fields | CRUD, wallet, tier |
| `routers/admin.py` | `plan_id` filter (L1147–1193), `active_licenses` (L2070–2129) | user list, payments |
| `routers/stats.py` | `licenses JOIN plans` fallbacks (L271–308), quota meters | credits + generation counts |
| `routers/redeem_codes.py` | `applicable_plan_id` (L251–286) | credit redeem |
| `services/usage_enforcement_service.py` | `_enforce_plan_quotas`, `_enforce_batch_daily_quotas`, `_subscription_covers_*`, `_is_wallet_daily_overage`, `_record_plan_allowance_ledger`, `_sync_plan_usage_reporting` | v3 charge, fail-absorb |
| `services/v3/store.py` | `get_plan_for_user`, `get_plan_for_web_subscription`, `get_active_free_plan` | lots, wallet |
| `services/v3/credits_only_billing_service.py` | `resolve_charge_plan`, `plan_id` | quote/charge/refund |
| `services/v3/wallet_sync.py` | `ensure_period_grant` | pack expiry, balance sync |
| `services/web_music_service.py` | plan checks | pack entitlement |
| `repositories/user_repo.py` | `plan_name`, `is_free` filters (L368–403) | tier filter |
| `models/domain.py`, `models/schemas.py` | Plan/License/plan fields | tier fields |
| `config.py` | `plan_monthly_overage_allowed` | |

### 3.3 Add

| File | Purpose |
|---|---|
| `services/tier_service.py` | already written — `is_pro`, `get_tier`, `tiers_for`, `tier_sql` |
| `services/product_access.py` | `require_pro` dependency for desktop-only routes |
| `repositories/credit_repo.py` | **lot decrement on spend** (FIFO by expiry) + refund restore — implemented |
| `services/signup_grant.py` | 50-credit one-time grant lot (replaces the Free plan grant) |
| `repositories/credit_repo.add_credits` | add a `create_lot` policy: admin/invite/referral create a lot; pack billing already inserts one and passes `create_lot=False` |
| `services/credit_invariants.py` | extend with `balance == SUM(live lots)` check |
| `tests/test_tier_gate.py` | Free blocked from desktop, Pro allowed |
| `tests/test_pack_expiry_tier.py` | expiry → Free, credits kept for legacy conversion |
| `tests/test_wallet_lot_invariant.py` | spend/refund/expiry keep the invariant |

### 3.4 Critical spend-path fix

Every charge must, in one transaction:
1. `SELECT ... FOR UPDATE` the live lots ordered by `expires_at NULLS LAST, created_at`.
2. Decrement `remaining_units` until the amount is covered.
3. Decrement `credit_wallets.balance`.
4. Insert `credit_transactions`.

Without this, the drift returns and `is_pro` lies.

**Acceptance:** `pytest platform_api/tests` green; pack checkout works; no `plans`/`licenses` SQL remains (`rg "FROM plans|JOIN plans|FROM licenses"` returns 0).

---

## 4. Phase 3 — Admin portal

| # | Task | File |
|---|---|---|
| 3.1 | Delete Plans page | `src/pages/plans/*` |
| 3.2 | Delete Licenses page | `src/pages/licenses/*` |
| 3.3 | Remove plan hooks | `src/hooks/use-plans*`, `use-licenses*`, plan mutations in `use-users` |
| 3.4 | User detail: remove Plan card, quota table, top-up dialog, add-on fields | `src/pages/users/user-detail.tsx` (L592–611, L646–708) |
| 3.5 | User list: replace plan filter with **Tier** (`All / Free / Pro`) | `src/pages/users/*` |
| 3.6 | Sidebar: remove Plans, Licenses | `src/components/layout/sidebar*` |
| 3.7 | Add **Customers** view: Pro users, credits, last purchase, expiry | new page |

**Acceptance:** admin builds; user detail shows Tier + wallet + purchases only; no "plan" string in the UI.

---

## 5. Phase 4 — Web (`camxora.com`)

| # | Task | File |
|---|---|---|
| 4.1 | Pricing page = credit packs only | `app/(site)/pricing/page.tsx` |
| 4.2 | Remove upgrade/renew/subscribe CTAs | site components |
| 4.3 | Account/dashboard: Tier + credits + expiry | account pages |
| 4.4 | Remove plan API helpers | `lib/*-api.ts` |

**Acceptance:** no plan words; "Buy credits" works end-to-end.

---

## 6. Phase 5 — Desktop (`camxora_python`)

| # | Task | File |
|---|---|---|
| 5.1 | Rename upgrade dialog → buy credits (packs only) | `features/account/views/upgrade_plans_dialog.py` |
| 5.2 | Gate message: "Buy a credit pack to unlock" | `features/account/views/auth_view.py` |
| 5.3 | Remove Plan card + quota meters | `features/dashboard/views/dashboard_view.py`, `widgets/remaining_month_card.py` |
| 5.4 | Remove plan models/fields | `shared/models/platform.py`, `shared/models/auth.py` |
| 5.5 | Remove plan API calls | `shared/services/platform_api.py` |

**Acceptance:** desktop signs in, shows Free/Pro + credits, blocks Free from studio, no plan text.

---

## 7. Phase 6 — Deploy and verify

| # | Task |
|---|---|
| 6.1 | Deploy backend + migration together (low traffic) |
| 6.2 | Run the 4 acceptance queries |
| 6.3 | Smoke: pack purchase → Pro; spend → balance + lots drop; expiry → Free |
| 6.4 | Monitor 24h: invariant check, 5xx, checkout |
| 6.5 | Announce to users |

**Rollback:** restore snapshot (fastest) or `alembic downgrade 173` (renames archives back; FK columns/lots are not restored).

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Dropping `plans` cascades `billing_payments` | Drop `billing_payments.plan_id` **before** `plans` |
| DistroKid lost with `licenses` | Copy to `users` first (migration step 0) |
| Credits drift returns | Lot decrement in the same transaction + nightly invariant |
| Free users blocked unexpectedly | 50 signup credits preserved; test login on staging |
| Pack checkout breaks with billing trim | Keep pack routes; integration test before deploy |
| Wrong expiry | Use source `expires_at`, no `now()+30d` |

---

## 9. Task board

| Phase | Task | Est. | Status |
|---|---|---|---|
| 0 | Snapshot + baseline | 0.5d | 🟡 snapshot running |
| 0 | Freeze plan sales | 0.5d | ⬜ |
| 1 | Migration 174 + dry-run | 1d | 🟡 staging restore + verify |
| 2 | Backend removal + spend fix | 2–3d | ✅ tests green |
| 3 | Admin UI | 1–2d | ⬜ |
| 4 | Web UI | 1d | ⬜ |
| 5 | Desktop UI | 1–2d | ⬜ |
| 6 | Deploy + verify | 0.5d | ⬜ |
