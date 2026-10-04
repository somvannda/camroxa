# Landing/billing: Suno-style credit-pack value framing + production pricing parity

## Summary

The public landing page and the user billing page now present each credit pack
the way Suno does — tier name, **songs**, **cost per song**, **credits per $1**
and the volume bonus — instead of only "N credits / $X". All of it is derived
from the live `credit_packs` and `pricing` rows, so admin edits propagate with
no second price list to maintain.

While verifying, we found the **local dev DB had drifted from production**:
production/sandbox serve `2,500 / 10,000 / 20,000 / 33,000` credits with
`music = 10`, while local held the migration-0015 values
`3,500 / 11,000 / 23,000 / 40,000` with `music = 15`. A new migration
(`0025`) converges local/sandbox onto the live production values, and the stale
seed scripts were corrected so a re-seed cannot reintroduce the old ladder.

## Product impact

- Landing pricing cards show, per pack: tier, credits, bonus credits, `≈ songs`,
  cost per song and credits per $1, with **Most popular** / **Best value**
  badges. Hero shows "from $0.015 / song".
- "Best value" is awarded to the highest credits-per-$1 pack, not blindly to the
  largest, so a non-monotonic ladder is not mislabelled.
- Copy and FAQ describe a generation as **10 credits → 2 songs** (the live
  value), and no longer hardcode a number that can drift.
- No change to how credits are charged, stored, or granted.

## Technical impact

- `musicapi/web-user/lib/packs.ts` (new in the prior commit; updated here)
  - `FALLBACK_PACKS` and `DEFAULT_MUSIC_COST` now mirror production
    (`2,500/10,000/20,000/33,000`, `music = 10`).
  - `buildPlans()` picks "Best value" by max credits-per-$1 (ties → larger pack)
    and clamps the bonus percentage at 0.
- `musicapi/web-user/app/page.tsx` — pricing copy/FAQ wording; values derived
  from the shared helper.
- `musicapi/web-user/app/dashboard/billing/page.tsx` — same value framing on the
  buy page (landed in the prior commit).
- `musicapi/migrations/0025_credit_pack_production_parity.sql` (new)
  - Sets `music = 10`; deletes non-ladder USD packs; corrects price/active on
    ladder rungs; inserts missing rungs. Written to be a **no-op where already at
    parity**, preserving pack ids (so historical `payment_transactions.pack_id`
    links survive).
- `musicapi/scripts/seed.ts`, `musicapi/scripts/update-pricing.ts` — music cost
  `15 → 10`; pack ladder `3,500/…` → `2,500/…`.

## Files touched

- `musicapi/web-user/lib/packs.ts`
- `musicapi/web-user/app/page.tsx`
- `musicapi/web-user/app/dashboard/billing/page.tsx` (prior commit)
- `musicapi/migrations/0025_credit_pack_production_parity.sql`
- `musicapi/scripts/seed.ts`
- `musicapi/scripts/update-pricing.ts`
- `docs/changelog/2026-10-04-musicapi-pricing-parity-and-pack-value.md`

## Migration / deploy

1. Run migrations (`scripts/migrate.ts`) — migration `0025` aligns packs +
   `music`. Safe/idempotent on sandbox and production (no-op at parity).
2. Rebuild `web-user` (landing + billing pages + `lib/packs.ts`).
3. No `web-admin` change (pack editing is unaffected).

## Tests

- `musicapi/web-user`: `tsc --noEmit` → clean; `eslint` on changed files → only
  the two pre-existing `<img>` warnings.
- Live production and sandbox `GET /pricing` fetched to confirm
  `2,500/10,000/20,000/33,000` and `music = 10`.
- Migration applied to local DB; re-query confirms
  `2,500/10,000/20,000/33,000` + `music = 10`.
- Dev-server SSR HTML rendered `10 credits / 2 songs`, `500 / 2,000 / 4,000 /
  6,600` songs, `$0.020 / $0.015 / $0.015 / $0.015`, `250 / 333 / 333 / 330`
  credits per $1, badges **Most popular** (Creator) and **Best value** (Pro).

## Follow-ups

- Production's `$100` pack (33,000 credits = 330 credits/$1) is slightly **worse
  per credit** than `$60` (20,000 = 333.33). The UI now reflects this honestly
  ("Best value" lands on Pro, and Studio shows "32% more" vs Pro's "33%").
  If unintended, bump the `$100` rung (e.g. 35,000 credits) via
  `/admin/credit-packs` and both pages update automatically.
- Other endpoint prices also differ between local and production (e.g. local
  `stems = 9` vs production `8`), out of scope for this pack-focused change.
