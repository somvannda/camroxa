# Credit packs: reprice to $5/1,000 · $10/2,300 · $20/5,500 · $30/8,800

## Summary

The USD credit-pack ladder is repriced:

| Price | Credits | Generations | Songs | Credits/$1 | Cost/song |
|---|---|---|---|---|---|
| $5 | 1,000 | 100 | 200 | 200 | $0.0250 |
| $10 | 2,300 | 230 | 460 | 230 | $0.0217 |
| $20 | 5,500 | 550 | 1,100 | 275 | $0.0182 |
| $30 | 8,800 | 880 | 1,760 | 293 | $0.0170 |

(`music` = 10 credits, 2 songs per generation → 5 credits/song.)

This supersedes the migration-0027 ladder ($10/2,500 · $20/5,800 · $30/9,000).
It is still a monotonic ladder — credits per $1 rise and cost per song falls
at every step — but it trims credits at $10/$20/$30 (higher margin per song).

## Product impact

- Landing + billing pages pick this up automatically (they render from
  `GET /pricing`; no code change). "Best value" stays on the $30 pack.
- No change to how credits are charged, granted or ledgered.

## Technical impact

- `musicapi/migrations/0028_credit_pack_reprice.sql` (new) — deletes the USD
  rows and inserts the new four. Values and price points change, so rows are
  replaced rather than remapped: historical transactions keep their own
  `credit_amount`/`amount`/`currency`, and `pack_id` is set NULL by the FK
  (same as 0015/0027).
- `musicapi/scripts/seed.ts`, `musicapi/scripts/update-pricing.ts` — same ladder.

## Files touched

- `musicapi/migrations/0028_credit_pack_reprice.sql`
- `musicapi/scripts/seed.ts`
- `musicapi/scripts/update-pricing.ts`
- `docs/changelog/2026-10-04-musicapi-credit-pack-reprice.md`

## Migration / deploy

1. Run migrations — `0028` replaces the ladder. Idempotent.
2. Applied to local, sandbox and production.

## Tests

- Migration applied locally; query confirms
  `1000/$5, 2300/$10, 5500/$20, 8800/$30`.
- Sandbox + production `GET /pricing` re-checked after deploy.

## Follow-ups

- If a sharper ladder vs Suno's per-song rates is wanted later, raise the middle
  rungs (e.g. $10/2,600, $20/6,000, $30/9,600).
