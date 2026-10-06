# Web-music paid plan grant was skipped (Free lot collision) — 2026-10-06

**Surfaces:** `platform_api/` (v3 period grants), `music_web/` (credit card + create CTA).

## Why

A just-paid CutLuy (music.camxora.com) subscriber kept only their leftover **Free**
credits instead of the plan allowance — e.g. a $5 Starter purchase showed
`1 / 1,999 credits · 1 left` and "Upgrade to Pro".

Root cause:

1. `PeriodGrantService.ensure_period_grant()` anchors a license-less account to
   `billing_month_start()` (calendar month). CutLuy subscribers have **no desktop
   license**, and `PlanRepository.get_user_active_subscription_context()` only joins
   `licenses`, so paid web subscribers also land on the calendar-month anchor.
2. A user who was on Free already holds a `grant` lot at that same
   `period_start`. `credit_wallet_lots` has a unique index on
   `(user_id, period_start) WHERE tag = 'grant'`
   (`migrations/versions/116_credits_only_v3.py`).
3. `insert_lot_if_absent` therefore returned `already_granted` and the paid
   allowance was **never minted**; `after_subscription_fulfill()` then zeroed the
   v2 counters. The wallet stayed at the depleted Free balance.
4. The `music_web` card then labelled a 1,000-credit pool as a 1,999 capacity
   because `computeCreditDisplay()` added `monthly_credits_used` (already
   `pool − remaining`) to the pool a second time.

This affected **every Free → paid upgrade in the same calendar month**, not just
one account (e.g. `iamduke1987` in
`docs/changelog/2026-10-05-web-music-credit-reconcile.md`).

## What changed

- `platform_api/services/v3/period_grant_service.py`
  `ensure_period_grant()`: when a period lot already exists but is **smaller**
  than the resolved plan's allowance, grow it to the new allowance and credit the
  difference through the ledger. Equivalent to the production reconcile formula
  `allowance − already granted`; idempotent once the lot holds the allowance.
- `platform_api/services/v3/store.py`: new `top_up_period_lot(lot_id, extra_units,
  max_units)` — a guarded `UPDATE ... WHERE amount_units + extra_units <= max_units`
  so concurrent grant sweeps cannot over-credit.
- `music_web/src/lib/credit-display.ts`: paid capacity is now
  `max(remaining, monthly_credits + topup_credits, 1)` (dropped the double-counted
  `monthly_credits_used`).
- `music_web/src/components/create-page-client.tsx`: refresh quota/balance on the
  `camxora:credits-updated` event so "Upgrade to Pro" clears after payment without
  a manual reload.

## Why not re-anchor to the subscription period

The earlier (unmerged) `fix/v3-period-grant-anchor` branch anchored the grant to
the web subscription period. That is unsafe on current `main`: the hourly
`grant_maintenance` sweep would see a new `period_start` and **double-grant**
every existing paid web subscriber, and yearly plans (`billing_cycle_days = 365`)
would stop refreshing monthly. The top-up approach fixes the collision without
changing the anchor, so Free, license, and yearly behaviour are unchanged.

## Verification

- `platform_api/tests/test_v3_period_grant.py` — new
  `test_period_grant_tops_up_free_lot_on_paid_upgrade` (Free 50 → paid 1000, one
  lot, idempotent) plus the existing suite: 9 passed.
- Full `platform_api` suite: 3164 passed; the 2 `test_media_router.py` logo
  failures are pre-existing and unrelated.
- `music_web` `npm test`: 50 passed (incl. a new capacity regression test).

## Follow-ups

- Backfill already-affected wallets (the code fix only corrects future sweeps);
  reuse `scripts/deploy/_reconcile_web_music_paid.py` or `top_up_period_lot`.
- `main` still lacks per-lot spend tracking (`atomic_deduct` FIFO / `consume_lots`)
  from `958c1640`; `credit_wallet_lots.remaining_units` stays stale until then.
- Reconcile the `platform_api/` "legacy" label in `AGENTS.md` with the fact that it
  serves `music.camxora.com` in production.
