# Packs-only billing — retire subscriptions, 30-day pack credits

**Date:** 2026-10-15
**Branch / PR:** `feat/packs-only-billing` — https://github.com/somvannda/camroxa/pull/386
**Surfaces:** `platform_api`, `music_web`, `admin_portal`, `website`
**Migration:** `platform_api/migrations/versions/136_packs_only_billing.py`

---

## Summary

`music.camxora.com` no longer sells subscriptions. Credit packs are the only
product, and pack credits now **expire 30 days from purchase**.

A pack purchase sets one **shared expiry date** for the whole wallet
("Option B"): the new pack lot *and* every other live lot (older packs, leftover
subscription allowance) are re-stamped to `purchase + 30 days`, so a balance ages
as a single unit instead of splitting into per-purchase buckets. Buying again
after running out therefore pushes the whole balance forward rather than creating
a second date.

Pack prices were raised to match the monthly plan allowances they replace, since
the old packs deliberately granted *fewer* credits per dollar than a plan.

## Product impact

- **Packs are the only purchasable product.** Pack ladder: $5 → 1,000 ·
  $10 → 2,300 · $20 → 5,500 *(new tier)* · $30 → 8,800.
- **Credits expire 30 days after the last purchase.** Unused credits are burned
  (clawed back) at that date; buying another pack resets the clock.
- **Grandfathered subscribers keep what they paid for.** Existing lot expiries are
  untouched: a monthly subscriber's allowance lapses at their current period end,
  a yearly subscriber's at the end of the prepaid term. After that they are
  pack-only.
- **Buying a pack also re-stamps leftover subscription credits** — a direct
  consequence of one shared expiry date, and accepted deliberately.
- **Free plan unchanged:** 50 credits per month (calendar-month grant).
- Old pack credits minted with `expires_at = NULL` are **not** retroactively
  burned; they are stamped to `purchase + 30 days` on the *next* pack purchase,
  otherwise they persist.

## Technical impact

- `V3BillingStore.expired_lots()` — renamed from `expired_grant_lots()`, and its
  tag filter now includes `'pack'`, so lapsed packs are swept.
- `V3BillingStore.restamp_live_lots(user_id, expires_at)` — new. Sets one shared
  expiry across live spendable lots. Two guards: it only ever **extends**
  (`expires_at IS NULL OR expires_at < $2`), so a prepaid yearly grant is never
  shortened; and it excludes `daily_grant`, so the Free daily cadence (if a plan
  ever grants daily again) keeps its midnight reset.
- `wallet_sync.PACK_CREDIT_VALIDITY = timedelta(days=30)`; `after_topup_fulfill`
  stamps the new lot and calls `restamp_live_lots`.
- `PeriodGrantService.expire_unused_grants` → `expire_lapsed_lots` (it now expires
  packs too, so the old name was wrong).
- `TopupService.purchase_topup` no longer requires an active subscription;
  `topup_purchases.web_subscription_id` is link-only metadata (already nullable).
- `SubscriptionRetiredError` (410) added to the exception hierarchy;
  `POST /subscriptions/purchase` and `POST /subscriptions/renewal` raise it.
  `GET /subscriptions/my-subscription` and `POST /subscriptions/cancel` stay live.
- `website/pricing` now reads the **public** `GET /api/v3/topups/packs` catalog
  rather than `/plans/public`, so the marketing ladder cannot drift from the app.

## Files touched

**platform_api**
- `services/v3/store.py` — `expired_lots()`, `restamp_live_lots()`
- `services/v3/wallet_sync.py` — `PACK_CREDIT_VALIDITY`, stamp + re-stamp
- `services/v3/period_grant_service.py` — `expire_lapsed_lots` + docstring
- `services/v2/topup_service.py` — removed the subscription gate
- `routers/v2_subscriptions.py` — 410 on purchase/renewal
- `routers/v3_billing.py` — renamed sweep call
- `exceptions.py` — `SubscriptionRetiredError`
- `migrations/versions/136_packs_only_billing.py` — pack re-price
- `tests/test_pack_credit_expiry.py` (new), `tests/test_wallet_sync.py`,
  `tests/test_v3_credits_only.py`, `tests/test_v3_period_grant.py`

**music_web** — `pricing-modal.tsx`, `pricing-page-client.tsx`,
`subscription-section.tsx`, `topup-modal.tsx`, `credit-balance-card.tsx`,
`credit-header.tsx`, `lib/credit-display.ts`; deleted `available-plans-grid.tsx`

**admin_portal** — `src/pages/plans/web-music-plans-section.tsx`

**website** — `src/app/pricing/page.tsx`, `src/app/pricing/pricing-cards.tsx`,
`src/app/page.tsx`

**docs** — this file, `docs/credits-only-plan-unification.md` (update banner)

## Migration / deploy

1. `alembic upgrade head` in `platform_api` (applies `136_packs_only_billing`).
   It re-prices `credit_packs`, adds the `$20` tier, and retires the off-ladder
   `mega` pack. It does **not** touch `credit_wallet_lots`.
2. Rebuild and deploy `music_web`, `admin_portal`, and `website`.
3. Deploy `platform_api`.
4. Sandbox first, then production.

No data migration for existing subscribers is required — their existing lots keep
their current expiry by design.

## Tests

- `platform_api/tests/test_pack_credit_expiry.py` (new, 8 tests): 30-day stamp;
  shared re-stamp of older packs + grants; `daily_grant` excluded; a later
  prepaid expiry never shortened; fulfill idempotency; lapsed-pack clawback;
  no overdraw on a spent wallet; plus two SQL contract tests pinning the tag list
  and the extend-only guard in `restamp_live_lots`.
- Fixed `test_wallet_sync.py`, whose fake store predated `restamp_live_lots`
  (a real regression the full suite caught, not just the targeted run).
- `platform_api`: 3195 passed, 1 failed.
- `music_web`: `tsc` clean, `npm test` 50/50.
- `admin_portal`: `tsc` clean (despite `noUnusedLocals: true`).
- `website`: `tsc` clean.
- `alembic heads` → single head `136_packs_only_billing`.

**Known failure (pre-existing, unrelated):**
`test_v3_period_grant.py::test_period_grant_uses_license_cycle_when_subscribed`
also fails on clean `main`. It is date-dependent — it hardcodes
`activated_at = 2026-09-15` and expects period start `2026-09-15`, but that 30-day
period has since rolled. Confirmed by stashing all changes and reproducing on
`main`.

## Follow-ups

- Fix the date-dependent `test_v3_period_grant` failure (its own tiny branch).
- Decide whether to delete the 4 orphaned website pricing components
  (`pricing-comparison-table.tsx`, `plan-channel-families.ts`,
  `profile-addon-pricing.tsx`, `usage-rates-section.tsx`) — pre-existing dead code,
  left untouched here.
- `admin_portal`'s `MANAGE_SUBSCRIPTION_PLANS` flag is a deliberate escape hatch so
  the plan editor can be re-enabled for a migration or a grandfathered-term fix;
  remove it once no plan rows are needed.
- Consider an expiry-warning email before the 30-day date (not requested).
