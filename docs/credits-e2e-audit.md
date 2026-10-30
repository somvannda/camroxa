# Credits end-to-end audit

**Scope:** signup → free trial → pack purchase → Pro → generation charge → refund → expiry → Free.
**Branch:** `chore/credits-only-two-tier` · **Date:** 2026-10-30
**Diagram:** `docs/credits-e2e-flow.html`

---

## 1. Method

Audited the live code paths (not intent), then replayed the migration on a restored
production copy (`camxora_staging_174`). Every statement below has a code reference.

---

## 2. End-to-end flow

### 2.1 Signup and the Free allowance

1. `POST /register` → user row, wallet row.
2. Email: grant only after confirmation. Google: auto-confirmed, grant immediately.
3. `ensure_signup_grant()` currently mints **one** 50-credit grant. The target rule is a
   **monthly reset**: 50 credits every 30 days, never more than 50 (no stacking).
4. Preview caps are already live (`services/web_music_previews.py`):
   - `PREVIEW_MODELS = ("V6", "V6_WILD")`
   - `PREVIEW_PER_MODEL_LIMIT = 1` per month
   - `PREVIEW_SECONDS = 60`
   - `V6_MINI` is always full-length.
5. Every model costs **10 credits**. The `credit_pricing` table currently says **15** — pending change.

**Result:** 50 credits, tier **Free**, 5 generations per month:
1 V6-Pro preview (10) + 1 V6-Wild preview (10) + 3 V6-Mini full (30) = 50.

### 2.2 Purchase (live web path)

1. `GET /api/v3/topups/packs/public` → active `credit_packs`.
2. `POST /api/v3/topups/purchase` → `TopupService.purchase_topup` → CutLuy checkout.
3. CutLuy webhook → `routers/webhooks_cutluy.py` → `TopupService.handle_topup_webhook`.
4. `sync_topup_pack()` → `WalletSyncService.after_topup_fulfill`:
   - `CreditLedger.grant()` → wallet + credits + `credit_transactions` row
   - `insert_lot(tag='pack', expires_at=now+30d)`
   - `restamp_live_lots()` → every live spendable lot moves to the new expiry
   - `has_transaction_ref()` makes the webhook idempotent.

**Result:** wallet increases, one `pack` lot, tier **Pro**.

### 2.3 Generation charge

1. Generation endpoint → `deduct_for_operation`.
2. Credits-only v3 is enabled → `_charge_via_v3` (plan coverage skipped).
3. `CreditsOnlyBillingService.quote()` → price from the `pricing` table only.
4. `atomic_deduct()` (`repositories/credit_repo.py`):
   - conditional `UPDATE credit_wallets ... WHERE balance >= amount`
   - `_consume_lots()` → FIFO by `expires_at NULLS LAST, created_at`
   - `credit_transactions` debit row — all in one transaction.

**Invariant after every charge:** `balance == SUM(live lots)`.

### 2.4 Refund

1. Provider failure → `refund` / `refund_once`.
2. Wallet + amount, `_restore_lots()` returns the credits to the most relevant live lot
   (pack first), or creates a non-expiring `grant` lot if none exists.
3. `refund_once` is keyed on `(user_id, reason, ref_id)` so retries cannot double-refund.

### 2.5 Expiry

1. `grant_maintenance` loop → `PeriodGrantService.expire_lapsed_lots`.
2. `store.expired_lots()` selects live lots with `expires_at <= now()` (grant, daily_grant,
   pack, referral).
3. Default: deduct the remaining units from the wallet (`v3_grant_expire`), zero the lot.
4. **No exception:** converted plan lots expire at their original plan date and are
   clawed back exactly like a pack. Every credit lot has an expiry ≤30 days.
5. Tier is derived, so no state transition is written: `is_pro` simply becomes false.

### 2.6 Admin and referral

- Admin adjustment → `add_credits(create_lot=True, lot_tag='admin', lot_expires_at=now+30d)` → wallet + admin lot (30-day expiry).
- Referral → `insert_referral_lot_if_absent` (30-day `referral` lot).
- Neither grants Pro.

---

## 3. State machine

```
                 signup +50
   Visitor ─────────────────► Free ◄──────────────┐
                               │                  │ pack expires
                               │ buy pack         │ (clawback, or
                               ▼                  │  legacy → grant)
                              Pro ────────────────┘
                               │
                               │ spend all
                               ▼
                          Exhausted
                               │ buy pack
                               └──────────► Pro
```

- **Free:** no live pack. 50 trial credits on signup; can generate while they last.
- **Pro:** ≥1 live pack lot. Desktop + web.
- **Exhausted:** Pro with 0 credits. Library + re-download only.
- Tier is **derived** (`tier_service.is_pro`), never stored.

---

## 4. Credit sources

| Source | Tag | Expiry | Pro? | Writer |
|---|---|---|---|---|
| Free monthly | `grant` | resets every 30 days | no | `free_monthly_grant` (pending) |
| Pack | `pack` | 30 days | **yes** | `wallet_sync` / `purchase_pack` |
| Admin | `admin` | never | no | `add_credits(create_lot=True)` |
| Referral | `referral` | 30 days | no | `insert_referral_lot_if_absent` |
| Legacy conversion | `pack` | original plan date (≤30d) | yes until expiry | migration 174 |

---

## 5. Invariants

```
balance == SUM(remaining_units) over live lots
tier == 'pro'  ⇔  EXISTS(live pack lot)
```

- Enforced on write by `atomic_deduct` + `_consume_lots` and `add_credits(create_lot)`.
- Checked nightly by `credit_invariants` (`wallet_lot_mismatches`), alerting via Telegram.
- Migration 174 rebuilds every wallet from `credit_wallets.balance`, so the invariant holds
  from the first second after cutover.

---

## 6. Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| F1 | **High** | Two pack-mint paths exist. | **Resolved** — live path is `/topups/purchase` (10 completed, latest 2026-10-30, all `chmaba`). `/billing/credit-pack/payments` has **0** `credit_pack` rows. Disable the latter. |
| F2 | **High** | Converted plan credits were clawed back on expiry, losing the value we promised to keep. | **Fixed** — legacy lots move to a non-expiring grant lot |
| F3 | Medium | Free users can generate while the 50 trial credits last. This is the approved trial model, but it means a non-buyer can produce a few songs. | Accepted (by design) |
| F4 | Medium | `users.py` returns `license_expires_at = None`, so admin/desktop cannot show the pack expiry. | Open — return `MAX(pack.expires_at)` |
| F5 | Low | `purchase_pack` now creates a pack lot; `wallet_sync` also inserts one. They use different refs. | Covered by F1 |
| F6 | Low | Admin quota top-up dialog remains but is unreachable. | Remove post-deploy |
| F7 | Low | `credit_invariants` multi-lot check only inspects `tag='grant'`; pack stacking is not flagged. | The new wallet/lot mismatch check covers the symptom |
| F8 | Info | `usage_tracking` still has the `music` counter; image/draft/video counters froze on 2026-09-22 and are unused. | No action |
| F9 | **High** | Monthly 50 reset. | **Fixed** — `free_monthly_grant` (reset, max 50, Free only). |
| F10 | **High** | V6 pricing. | **Fixed** — migration 176 sets V6 / V6_MINI / V6_WILD to 100,000 units (10 credits). |

---

## 7. Dry-run evidence

| Check | Result |
|---|---|
| Wallet invariant | 0 mismatches |
| Tier split | 11 Pro / 228 Free (2 new users since baseline) |
| Plan tables | 0 |
| `billing_payments` | 25 (history intact) |
| Plan FKs | 0 |
| Converted users | correct balances + original expiry |
| DistroKid | nothing enabled, nothing lost |

---

## 8. Recommendations

1. **Resolve F1 before deploy** — pick one pack-mint path. The web uses `/topups/purchase`;
   disable `/billing/credit-pack/payments` or make it call `sync_topup_pack`.
2. **F4** — return the live pack expiry from `users.py` so admin/desktop show the real date.
3. Keep the nightly invariant alert on; it would have caught the original 5,150-vs-0.11 drift.
4. Remove the dead plan modules and the unused quota dialog after deploy.
5. Add a regression test for the legacy-expiry conversion (remainder → grant, balance unchanged).

---

## 9. Verification after deploy

```sql
-- invariant
SELECT count(*) FROM credit_wallets w
WHERE w.balance <> COALESCE((
  SELECT SUM(remaining_units) FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
), 0);

-- tier split
SELECT CASE WHEN EXISTS (
  SELECT 1 FROM credit_wallet_lots l
  WHERE l.user_id = w.user_id AND l.tag='pack'
    AND l.remaining_units > 0
    AND (l.expires_at IS NULL OR l.expires_at > now())
) THEN 'pro' ELSE 'free' END, count(*)
FROM credit_wallets w GROUP BY 1;
```
