# Batch generation is a credit-pack feature (Free plan is single-song only)

**Date:** 2026-10-29
**Branch / PR:** `fix/web-batch-credits-only`
**Surfaces:** `music_web`, `camxora.com`, `platform_api`

---

## Summary

Batch generation on Web Create (5 / 10 / 20 songs) was gated on
`has_subscription`, which has been permanently `false` since subscriptions were
retired on 2026-10-15 (`docs/changelog/2026-10-15-packs-only-billing.md`). A
customer holding 8,731 credits was therefore blocked with *"Batch generation is
a Pro feature."* while a Free-plan customer with 50 credits could not batch
either — by design, but for the wrong reason.

Batch is now explicitly a **credit-pack feature**:

- **Free plan (50 credits/month)** — single songs only. Batch sizes above 1 stay
  locked and route to the pack modal.
- **Pack buyers** — batch 5 / 10 / 20 for as long as the wallet covers
  `credits_per_song × count`. No subscription, no "Pro" tier.
- **Grandfathered paid subscribers** — keep batch access.

The entitlement is the existing `premium_unlocked` flag (a pack was bought this
month, the wallet holds more than the Free monthly grant, or the account is a
grandfathered paid plan), so no new API field was introduced.

## Product impact

- Free plan: selecting 5 / 10 / 20 songs shows *"Batch generation comes with
  credit packs. Buy a pack to create N songs at once."*; Create is disabled and
  the CTA opens the pack modal.
- Pack buyers: batch works with no subscription. Insufficient credits still
  shows the top-up note (*"You need N credits…"*).
- Queue cap is no longer tiered (2 for unsubscribed → 20 for everyone), so a
  pack buyer's 5-song batch is not rejected at song 3 with *"You already have 2
  songs waiting"* while the Suno queue drains.
- `music.camxora.com` copy no longer says *Upgrade to Pro* (→ **Buy credits**).

## Technical impact

- `platform_api/services/web_music_service.py` — legacy (pre-v3) credit path now
  emits `premium_unlocked` via `_legacy_pack_unlocked()` (pack `topup_balance`
  or grandfathered `has_subscription`), so the quota payload always carries the
  entitlement. The v3 path already used
  `WebMusicChargeBridge.premium_unlocked()`.
- `platform_api/services/job_types.py` — `WEB_MUSIC_GENERATE_QUEUE_CAP_FREE`
  2 → 20 (both tiers share one number; credits bound the wallet).
- `music_web/src/components/create-page-client.tsx` — `batchRequiresUpgrade`
  is back, keyed on `quota.premium_unlocked` (falls back to
  `has_subscription` / `is_pro` for older payloads).
- `music_web/src/lib/create-submit-queue.ts` — `CREATE_MAX_QUEUE_FREE` 2 → 20.
- `camxora.com/components/CreateStudio.tsx` — same pack gate in `onSubmit`,
  `createDisabled`, and `batchWarning`.

## Migration / deploy

No migration. Deploy **`platform_api` first** (it must emit `premium_unlocked`
on every quota response), then rebuild `music_web` and `camxora.com`.

## Tests

- `platform_api/tests/test_web_music_batch_access.py` (new): Free plan with 50
  credits → `premium_unlocked: false`; pack wallet → `true`; legacy ledger maps
  `topup_balance` / grandfathered subscription correctly.
- `platform_api/tests/test_web_music_generate_queue.py` — shared 20 cap.
- `pytest platform_api/tests -k web_music` → 148 passed.
- `music_web`: `npm test` → 57 passed; `tsc --noEmit` clean (non-test files).
- `camxora.com`: `npm run typecheck` clean.

## Follow-ups

- `camxora.com` credit menu still renders `Plan: Pro | Free` from
  `quota.has_subscription`, so paying pack users read as *Free*. Replace with
  pack status (`premium_unlocked`) or drop the row.
- The account card labels the Free plan's monthly grant *"Credit reset monthly"*;
  with batch now pack-only, that label invites the same "why is my plan gone?"
  confusion.
- `_is_paid_queue_user()` still keys off `has_subscription`; harmless while both
  caps are 20, but it should move to `premium_unlocked` if the caps diverge again.
