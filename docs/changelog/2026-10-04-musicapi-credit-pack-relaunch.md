# Credit packs: relaunch with a $5–$30 ladder

## Summary

The USD credit-pack ladder is replaced with a new, lower-priced structure:

| Price | Credits | Generations | Songs | Credits/$1 | Cost/song |
|---|---|---|---|---|---|
| $5 | 1,000 | 100 | 200 | 200 | $0.0250 |
| $10 | 2,500 | 250 | 500 | 250 | $0.0200 |
| $20 | 5,800 | 580 | 1,160 | 290 | $0.0172 |
| $30 | 9,000 | 900 | 1,800 | 300 | $0.0167 |

(`music` = 10 credits, 2 songs per generation → 5 credits/song.)

## Product impact

- Cheaper entry point ($5) and a lower top price ($30); value per dollar rises
  monotonically and cost per song falls monotonically, so "Best value" lands on
  the $30 pack and "Most popular" on the $10 pack.
- Landing page + billing page pick this up automatically (they render from
  `GET /pricing`; no code change).

## Technical impact

- `musicapi/migrations/0027_credit_pack_relaunch.sql` (new) — deletes the old
  USD rows and inserts the new four. The price points changed, so rows are
  replaced rather than remapped: historical transactions keep their own
  `credit_amount`/`amount`/`currency`, and `pack_id` is set NULL by the FK
  (same as migration 0015).
- `musicapi/scripts/seed.ts`, `musicapi/scripts/update-pricing.ts` — same ladder
  so a manual seed/repricing can't reintroduce the old one.

## Files touched

- `musicapi/migrations/0027_credit_pack_relaunch.sql`
- `musicapi/scripts/seed.ts`
- `musicapi/scripts/update-pricing.ts`
- `docs/changelog/2026-10-04-musicapi-credit-pack-relaunch.md`

## Migration / deploy

1. Run migrations — `0027` replaces the ladder. Idempotent.
2. No frontend rebuild is strictly required (prices are fetched live), but a
   deploy ships the matching seed scripts.
3. Applied to local, sandbox and production.

## Tests

- Migration applied locally; query confirms
  `1000/$5, 2500/$10, 5800/$20, 9000/$30`.
- `GET /pricing` on sandbox and production to be re-checked after deploy.

## Follow-ups

- None. If the $20→$30 step ever needs smoothing, adjust the rungs in
  `/admin/credit-packs`.
