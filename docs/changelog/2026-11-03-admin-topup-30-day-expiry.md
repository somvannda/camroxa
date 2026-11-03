# Admin comps now expire and unlock the studio, like a pack

**Date:** 2026-11-03
**Surfaces:** `platform_api`, `admin_portal`
**Migration:** none

---

## Summary

`CreditService.admin_adjust` has been minting an `admin` credit lot stamped
`now + 30 days` — the wallet balance and the lot move in the same transaction —
but the rest of the system only knew about `pack` lots. Three gaps followed:

| Surface | Was | Now |
|---|---|---|
| `expired_lots()` sweep | tags `grant`, `daily_grant`, `pack`, `referral` | **+ `admin`** |
| `has_paid_desktop_access()` | `tag = 'pack'` | **`tag IN ('pack', 'admin')`** |
| `has_completed_topup_this_month()` | `topup_purchases` only | **+ positive `admin_adjustment:` row this month** |
| Telegram ops badge | `topup_purchases` only | **same ledger clause** |

Net effect: an admin credit is the only credit in the wallet that never burned,
and a comped user got a spendable balance the desktop gate rejected. Both now
follow the pack rules, and a comped Free user keeps the month's premium access
instead of dropping back to V6-Mini the moment the balance reaches the 50-credit
grant.

## Product impact

- **Admin credit burns 30 days after the comp**, exactly like a pack. Unused
  admin credit is clawed back by the existing grant sweep.
- **Desktop studio access now follows admin credit.** A licence-less user who is
  topped up by an admin can open the studio while that credit is live.
- **A comp unlocks the month like a purchase.** V6-Pro / V6-Wild stay available
  to a comped Free user until month end, and the ops feed badges the account
  **PAID** rather than FREE.
- **The plan is deliberately untouched.** A top-up is consumption, not
  entitlement: assigning a paid plan from it would grant unrestricted model
  access regardless of balance, so 100 comped credits would buy permanent Pro
  treatment. Comping a plan stays the separate, audited `POST /licenses` action.
- **A comp is still not a sale.** No `topup_purchases` row is written, so the
  comp stays out of revenue, receipts, purchase refunds and the referral reward.
- **Legacy `topup_credits_balance` is deliberately not decremented.** The pack
  flow's `subtract_web_topup()` reverses the `091` trigger, which credits that
  legacy column when a purchase carries a `web_subscription_id`. A comp fires no
  trigger, so mirroring the call would run `GREATEST(0, balance - amount)` against
  credits that were never incremented and silently shrink a grandfathered
  subscriber's balance.
- **Comps and purchases stay distinguishable** in the admin lots table: comps are
  `admin`, purchases are `pack`. No synthetic pack lot is minted, so the lot
  ledger never double-counts a single comp.

## Technical impact

- `V3BillingStore.expired_lots()` — `'admin'` added to both tag lists.
- `LicenseRepository.has_paid_desktop_access()` — gate widened to
  `lot.tag IN ('pack', 'admin')`.
- `V3BillingStore.has_completed_topup_this_month()` — keeps the
  `topup_purchases` clause (so a refunded pack still stops counting) and adds a
  `UNION ALL` on positive `admin_adjustment:%` rows in `credit_transactions` this
  month. Name unchanged to avoid rippling callers; the docstring now says
  "gained paid credit".
- `telegram_ops_alert_service._user_snapshot()` — same `OR EXISTS` clause, so the
  badge cannot disagree with the premium gate. Deductions never match
  (`direction = 'credit'`, `amount > 0`).
- `admin_portal` user-detail top-up dialog states the 30-day validity.

No application code changed in `credit_service` / `credit_repo`: the lot was
already there.

## Files touched

**platform_api**
- `services/v3/store.py` — expiry sweep + paid-month probe
- `repositories/license_repo.py` — desktop gate
- `services/telegram_ops_alert_service.py` — PAID badge
- `tests/test_admin_topup_parity.py` (new) — 4 contract tests
- `tests/test_telegram_ops_alert_service.py` — snapshot SQL counts admin top-ups

**admin_portal**
- `src/pages/users/user-detail.tsx` — dialog copy

**docs** — this file, `platform_api/CHANGELOG.md`, `admin_portal/CHANGELOG.md`

## Deploy

No migration. Deploy `platform_api`, then rebuild `admin_portal` (copy-only; the
API works without it). Expiry rides the existing grant-maintenance sweep.

## Sandbox smoke test

1. Top up 100 credits to a licence-less user with no pack history.
2. `GET /api/v3/users/{id}/credits` — an `admin` lot exists with `expires_at` ~30 days out.
3. `GET /users/me` — `desktop_access: true` while the lot is live.
4. `GET /api/v3/web-music/quota` — `premium_unlocked: true`; a generation report
   badges **PAID** on Telegram.
5. Deduct credits — no new lot appears, and the month stays unlocked for a prior comp.
6. Backdate the lot past `NOW()` and run the grant sweep — the remaining balance is clawed back.

## Decisions

- **No backfill (option C: fix forward only).** Wallets whose balance exceeds
  their live-lot remainder are visible with a read-only query (wallet balance
  minus live-lot `remaining_units`), but that delta is not only admin comps: it
  also contains legacy pre-`create_lot` credits and conversion credits that were
  meant to be permanent. Stamping the whole delta with a 30-day expiry would burn
  real customer value, and attributing it to admin adjustments alone is not
  provable from the ledger. Existing balances therefore keep their current
  behaviour; every comp issued from this release onward is swept correctly.

## Known gaps (out of scope)

- A manual deduction leaves lot `remaining_units` overstated. Harmless — the sweep
  clamps with `min(remaining, balance)` — but the admin lots table reads high
  until expiry.
