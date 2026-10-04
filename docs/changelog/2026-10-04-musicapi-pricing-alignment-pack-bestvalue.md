# Pricing: production parity, a fixed $100 rung, and DB-only landing prices

## Summary

Follow-up to `2026-10-04-musicapi-pricing-parity-and-pack-value.md`. Three
loose ends from that work are now closed:

1. **The $100 pack was mispriced** — 33,000 credits = 330 credits/$1, *less*
   than the $60 pack (333.33/$1), which inverted the volume ladder and made the
   "Best value" badge land on Pro. It is now **35,000 credits (350/$1)**, so the
   largest pack is genuinely the best rate and carries the badge.
2. **Local/fresh pricing tables diverged from production.** Every per-endpoint
   credit cost is now aligned with the live production/sandbox snapshot.
3. **The landing page no longer hardcodes pack prices.** It renders purely from
   `GET /pricing`, with loading and error/empty states instead of a baked-in
   fallback list, so there is no second price source that can drift.

## Product impact

- Landing pack cards: `$10 → 2,500`, `$30 → 10,000`, `$60 → 20,000`,
  `$100 → 35,000`. Studio is now **Best value**; Creator stays **Most popular**.
- If `GET /pricing` is unreachable the section shows a short "pricing
  temporarily unavailable" note (and a skeleton while loading) rather than
  possibly-stale numbers.
- Endpoint charges (lyrics, stems, wav_download, etc.) are identical across
  local, sandbox and production.
- No change to how credits are charged, granted or ledgered.

## Technical impact

- `musicapi/migrations/0026_pricing_production_alignment.sql` (new)
  - `UPDATE credit_packs SET amount = 35000 WHERE amount = 33000` (row updated
    in place, so `payment_transactions.pack_id` survives).
  - A temp snapshot table applies the 42-endpoint production cost list via
    UPDATE + `INSERT … WHERE NOT EXISTS`. Idempotent and a no-op where already at
    parity.
- `musicapi/scripts/seed.ts`, `musicapi/scripts/update-pricing.ts` — carry the
  same production snapshot + `$100 = 35,000`, so a manual seed/repricing can't
  reintroduce the old values.
- `musicapi/web-user/lib/packs.ts` — removed `FALLBACK_PACKS`; the file now only
  holds the derivation helpers. `DEFAULT_MUSIC_COST` remains solely as a
  divide-by-zero guard.
- `musicapi/web-user/app/page.tsx` — `packs` starts `null`; renders the grid
  once `/pricing` responds, a skeleton while loading, and explicit
  error/empty states otherwise. The "from $X/song" hero stat only appears once
  real data is present.

## Files touched

- `musicapi/migrations/0026_pricing_production_alignment.sql`
- `musicapi/scripts/seed.ts`
- `musicapi/scripts/update-pricing.ts`
- `musicapi/web-user/lib/packs.ts`
- `musicapi/web-user/app/page.tsx`
- `docs/changelog/2026-10-04-musicapi-pricing-alignment-pack-bestvalue.md`

## Migration / deploy

1. Run migrations — `0026` bumps the `$100` pack and aligns endpoint costs.
   Safe/idempotent on sandbox and production.
2. Rebuild `web-user`.
3. No `web-admin` change.

## Tests

- `musicapi/web-user`: `tsc --noEmit` clean; `eslint` clean (pre-existing
  `<img>` warnings only); `next build` succeeds.
- Migration applied locally; re-query shows packs `2500/10000/20000/35000` and
  all 42 endpoint rows equal to production.
- Verified live production + sandbox `GET /pricing` snapshots matched before
  writing the migration.

## Follow-ups

- Deployed to sandbox then production (see deploy log). No known open items.
